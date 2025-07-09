"""
Multi-Engine OCR System with Intelligent Fallback.

This module provides a sophisticated OCR system that can use multiple engines
with intelligent fallback, quality comparison, and automatic engine selection.
"""

import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics

from .base import OCREngine, OCRResult, OCROptions, OCREngineManager
from ..utils.logger import get_logger
from ..utils.cache_manager import create_cache_manager


@dataclass
class EngineQualityMetrics:
    """Quality metrics for an OCR engine."""
    
    engine_name: str
    confidence: float
    processing_time: float
    word_count: int
    character_count: int
    success_rate: float = 1.0
    error_count: int = 0
    
    def calculate_quality_score(self) -> float:
        """Calculate overall quality score (0.0 - 1.0)."""
        # Weighted scoring
        confidence_weight = 0.4
        speed_weight = 0.2
        success_weight = 0.3
        content_weight = 0.1
        
        # Normalize processing time (lower is better, max 30 seconds)
        speed_score = max(0.0, 1.0 - (self.processing_time / 30.0))
        
        # Content richness score
        content_score = min(1.0, (self.word_count + self.character_count / 10) / 100)
        
        total_score = (
            self.confidence * confidence_weight +
            speed_score * speed_weight +
            self.success_rate * success_weight +
            content_score * content_weight
        )
        
        return max(0.0, min(1.0, total_score))


@dataclass
class EnginePreferences:
    """User preferences for engine selection."""
    
    preferred_engines: List[str] = field(default_factory=list)
    fallback_engines: List[str] = field(default_factory=list)
    quality_threshold: float = 0.7
    max_processing_time: float = 60.0
    enable_parallel_processing: bool = False
    enable_quality_comparison: bool = True
    
    # Engine-specific settings
    engine_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class MultiEngineOCR:
    """Multi-engine OCR system with intelligent selection and fallback."""
    
    def __init__(self, preferences: Optional[EnginePreferences] = None, 
                 enable_cache: bool = True, cache_dir: Optional[str] = None):
        """
        Initialize multi-engine OCR system.
        
        Args:
            preferences: Engine preferences and configuration
            enable_cache: Whether to enable intelligent caching
            cache_dir: Directory for cache storage
        """
        self.preferences = preferences or EnginePreferences()
        self.logger = get_logger("multi_engine_ocr")
        
        # Engine manager
        self.engine_manager = OCREngineManager()
        
        # Cache system
        self.enable_cache = enable_cache
        self.cache_manager = None
        if enable_cache:
            try:
                self.cache_manager = create_cache_manager(cache_dir)
                self.logger.info("Cache inteligente ativado")
            except Exception as e:
                self.logger.warning(f"Erro ao inicializar cache: {e}")
                self.enable_cache = False
        
        # Quality tracking
        self.engine_metrics: Dict[str, List[EngineQualityMetrics]] = {}
        self.engine_stats: Dict[str, Dict[str, float]] = {}
        
        # Performance tracking
        self.total_processed = 0
        self.total_success = 0
        self.processing_history: List[Dict[str, Any]] = []
        
    def register_engine(self, engine: OCREngine, make_default: bool = False):
        """Register an OCR engine."""
        self.engine_manager.register_engine(engine, make_default)
        
        # Initialize metrics tracking
        if engine.name not in self.engine_metrics:
            self.engine_metrics[engine.name] = []
            self.engine_stats[engine.name] = {
                'avg_confidence': 0.0,
                'avg_processing_time': 0.0,
                'success_rate': 1.0,
                'total_processed': 0
            }
        
        self.logger.info(f"Registered OCR engine: {engine.name}")
    
    def process_file(self, file_path: Union[str, Path], 
                    options: Optional[OCROptions] = None) -> OCRResult:
        """
        Process file using the best available engine with intelligent caching.
        
        Args:
            file_path: Path to file
            options: OCR processing options
            
        Returns:
            OCR result from best engine or cache
        """
        if options is None:
            options = OCROptions()
        
        file_path = Path(file_path)
        
        # Tentar cache primeiro
        if self.enable_cache and self.cache_manager:
            cached_result = self._try_get_from_cache(file_path, options)
            if cached_result:
                return cached_result
        
        # Processar se não estiver em cache
        if self.preferences.enable_parallel_processing:
            result = self._process_with_parallel_engines(file_path, options)
        else:
            result = self._process_with_sequential_fallback(file_path, options)
        
        # Salvar no cache se processamento foi bem-sucedido
        if result and result.success and self.enable_cache and self.cache_manager:
            self._save_to_cache(file_path, result, options)
        
        return result
    
    def _process_with_sequential_fallback(self, file_path: Path, 
                                        options: OCROptions) -> OCRResult:
        """Process with sequential engine fallback."""
        engine_order = self._determine_engine_order(file_path)
        
        best_result = None
        attempts = []
        
        for engine_name in engine_order:
            engine = self.engine_manager.get_engine(engine_name)
            if not engine or not engine.is_available():
                continue
            
            self.logger.info(f"Processing {file_path.name} with {engine_name}")
            
            try:
                result = engine.process_file(file_path, options)
                attempts.append(result)
                
                # Track metrics
                self._update_engine_metrics(engine_name, result)
                
                if result.success:
                    # Check if quality is acceptable
                    quality_score = self._calculate_result_quality(result)
                    
                    if quality_score >= self.preferences.quality_threshold:
                        best_result = result
                        break
                    elif best_result is None or quality_score > self._calculate_result_quality(best_result):
                        best_result = result
                        
            except Exception as e:
                self.logger.error(f"Engine {engine_name} failed: {e}")
                
                # Create error result for tracking
                error_result = OCRResult(
                    text="",
                    confidence=0.0,
                    pages=[],
                    processing_time=0.0,
                    engine=engine_name,
                    language=options.language,
                    file_path=str(file_path),
                    success=False,
                    error_message=str(e)
                )
                
                self._update_engine_metrics(engine_name, error_result)
                attempts.append(error_result)
        
        # Update global stats
        self.total_processed += 1
        if best_result and best_result.success:
            self.total_success += 1
        
        # Log processing attempt
        self._log_processing_attempt(file_path, attempts, best_result)
        
        return best_result or self._create_failure_result(file_path, options, attempts)
    
    def _process_with_parallel_engines(self, file_path: Path,
                                     options: OCROptions) -> OCRResult:
        """Process with parallel engines for quality comparison."""
        available_engines = self.engine_manager.get_available_engines()
        
        if not available_engines:
            return self._create_failure_result(file_path, options, [])
        
        # Limit parallel processing to 3 engines for efficiency
        engines_to_use = available_engines[:3]
        
        results = {}
        
        with ThreadPoolExecutor(max_workers=len(engines_to_use)) as executor:
            # Submit all engines
            future_to_engine = {}
            for engine_name in engines_to_use:
                engine = self.engine_manager.get_engine(engine_name)
                if engine and engine.is_available():
                    future = executor.submit(engine.process_file, file_path, options)
                    future_to_engine[future] = engine_name
            
            # Collect results
            for future in as_completed(future_to_engine):
                engine_name = future_to_engine[future]
                try:
                    result = future.result(timeout=self.preferences.max_processing_time)
                    results[engine_name] = result
                    self._update_engine_metrics(engine_name, result)
                except Exception as e:
                    self.logger.error(f"Parallel engine {engine_name} failed: {e}")
                    
                    error_result = OCRResult(
                        text="",
                        confidence=0.0,
                        pages=[],
                        processing_time=0.0,
                        engine=engine_name,
                        language=options.language,
                        file_path=str(file_path),
                        success=False,
                        error_message=str(e)
                    )
                    
                    results[engine_name] = error_result
                    self._update_engine_metrics(engine_name, error_result)
        
        # Select best result
        best_result = self._select_best_result(results)
        
        # Update stats
        self.total_processed += 1
        if best_result and best_result.success:
            self.total_success += 1
        
        # Log processing attempt
        self._log_processing_attempt(file_path, list(results.values()), best_result)
        
        return best_result or self._create_failure_result(file_path, options, list(results.values()))
    
    def _determine_engine_order(self, file_path: Path) -> List[str]:
        """Determine optimal engine order based on file type and performance."""
        # Start with user preferences
        engine_order = self.preferences.preferred_engines.copy()
        
        # Add fallback engines
        engine_order.extend(self.preferences.fallback_engines)
        
        # Add remaining available engines sorted by performance
        available = self.engine_manager.get_available_engines()
        remaining = [e for e in available if e not in engine_order]
        
        # Sort by average quality score
        remaining.sort(key=lambda e: self._get_engine_average_quality(e), reverse=True)
        engine_order.extend(remaining)
        
        # Remove duplicates while preserving order
        seen = set()
        ordered = []
        for engine in engine_order:
            if engine not in seen and engine in available:
                seen.add(engine)
                ordered.append(engine)
        
        return ordered
    
    def _select_best_result(self, results: Dict[str, OCRResult]) -> Optional[OCRResult]:
        """Select best result from parallel processing."""
        successful_results = {k: v for k, v in results.items() if v.success}
        
        if not successful_results:
            # Return best failed result
            if results:
                return max(results.values(), key=lambda r: r.confidence)
            return None
        
        # Calculate quality scores for successful results
        scored_results = []
        for engine_name, result in successful_results.items():
            quality_score = self._calculate_result_quality(result)
            scored_results.append((quality_score, result))
        
        # Return result with highest quality score
        scored_results.sort(reverse=True)
        return scored_results[0][1]
    
    def _calculate_result_quality(self, result: OCRResult) -> float:
        """Calculate quality score for a result."""
        if not result.success:
            return 0.0
        
        # Factors for quality assessment
        confidence_factor = result.confidence
        
        # Text richness factor
        word_density = len(result.text.split()) / max(1, result.processing_time)
        richness_factor = min(1.0, word_density / 50.0)  # Normalize to 50 words/second
        
        # Processing efficiency factor
        efficiency_factor = max(0.0, 1.0 - (result.processing_time / 30.0))
        
        # Combined score
        quality_score = (
            confidence_factor * 0.5 +
            richness_factor * 0.3 +
            efficiency_factor * 0.2
        )
        
        return max(0.0, min(1.0, quality_score))
    
    def _update_engine_metrics(self, engine_name: str, result: OCRResult):
        """Update metrics for an engine."""
        metrics = EngineQualityMetrics(
            engine_name=engine_name,
            confidence=result.confidence,
            processing_time=result.processing_time,
            word_count=result.word_count,
            character_count=result.character_count,
            success_rate=1.0 if result.success else 0.0,
            error_count=0 if result.success else 1
        )
        
        # Add to metrics history
        self.engine_metrics[engine_name].append(metrics)
        
        # Keep only last 100 metrics per engine
        if len(self.engine_metrics[engine_name]) > 100:
            self.engine_metrics[engine_name] = self.engine_metrics[engine_name][-100:]
        
        # Update running averages
        self._update_engine_stats(engine_name)
    
    def _update_engine_stats(self, engine_name: str):
        """Update running statistics for an engine."""
        metrics = self.engine_metrics[engine_name]
        if not metrics:
            return
        
        # Calculate averages
        confidences = [m.confidence for m in metrics if m.success_rate > 0]
        processing_times = [m.processing_time for m in metrics]
        success_rates = [m.success_rate for m in metrics]
        
        self.engine_stats[engine_name] = {
            'avg_confidence': statistics.mean(confidences) if confidences else 0.0,
            'avg_processing_time': statistics.mean(processing_times),
            'success_rate': statistics.mean(success_rates),
            'total_processed': len(metrics)
        }
    
    def _get_engine_average_quality(self, engine_name: str) -> float:
        """Get average quality score for an engine."""
        if engine_name not in self.engine_metrics:
            return 0.5  # Default for new engines
        
        metrics = self.engine_metrics[engine_name]
        if not metrics:
            return 0.5
        
        # Calculate average quality score
        quality_scores = [m.calculate_quality_score() for m in metrics]
        return statistics.mean(quality_scores)
    
    def _log_processing_attempt(self, file_path: Path, attempts: List[OCRResult], 
                              best_result: Optional[OCRResult]):
        """Log processing attempt for analysis."""
        attempt_data = {
            'timestamp': time.time(),
            'file_path': str(file_path),
            'file_size': file_path.stat().st_size if file_path.exists() else 0,
            'attempts': [
                {
                    'engine': result.engine,
                    'success': result.success,
                    'confidence': result.confidence,
                    'processing_time': result.processing_time,
                    'word_count': result.word_count,
                    'error': result.error_message
                }
                for result in attempts
            ],
            'best_engine': best_result.engine if best_result else None,
            'best_confidence': best_result.confidence if best_result else 0.0,
            'total_engines_tried': len(attempts)
        }
        
        self.processing_history.append(attempt_data)
        
        # Keep only last 500 attempts
        if len(self.processing_history) > 500:
            self.processing_history = self.processing_history[-500:]
    
    def _create_failure_result(self, file_path: Path, options: OCROptions,
                             attempts: List[OCRResult]) -> OCRResult:
        """Create failure result when all engines fail."""
        error_messages = [attempt.error_message for attempt in attempts if attempt.error_message]
        combined_error = "; ".join(error_messages) if error_messages else "All engines failed"
        
        return OCRResult(
            text="",
            confidence=0.0,
            pages=[],
            processing_time=sum(attempt.processing_time for attempt in attempts),
            engine="multi_engine",
            language=options.language,
            file_path=str(file_path),
            success=False,
            error_message=combined_error
        )
    
    def get_engine_statistics(self) -> Dict[str, Any]:
        """Get comprehensive engine statistics."""
        stats = {
            'total_processed': self.total_processed,
            'total_success': self.total_success,
            'overall_success_rate': self.total_success / max(1, self.total_processed),
            'engines': {}
        }
        
        for engine_name, engine_stats in self.engine_stats.items():
            engine = self.engine_manager.get_engine(engine_name)
            
            stats['engines'][engine_name] = {
                'available': engine.is_available() if engine else False,
                'metrics': engine_stats,
                'quality_score': self._get_engine_average_quality(engine_name),
                'recent_attempts': len([
                    m for m in self.engine_metrics.get(engine_name, [])
                    if time.time() - getattr(m, 'timestamp', 0) < 3600  # Last hour
                ])
            }
        
        return stats
    
    def get_recommendations(self) -> Dict[str, Any]:
        """Get engine recommendations based on performance."""
        stats = self.get_engine_statistics()
        
        # Find best performing engines
        engine_scores = [
            (name, data['quality_score'])
            for name, data in stats['engines'].items()
            if data['available']
        ]
        engine_scores.sort(key=lambda x: x[1], reverse=True)
        
        recommendations = {
            'recommended_primary': engine_scores[0][0] if engine_scores else None,
            'recommended_fallback': [name for name, _ in engine_scores[1:3]],
            'avoid_engines': [
                name for name, data in stats['engines'].items()
                if data['metrics']['success_rate'] < 0.5
            ],
            'optimization_suggestions': []
        }
        
        # Add optimization suggestions
        if stats['overall_success_rate'] < 0.8:
            recommendations['optimization_suggestions'].append(
                "Consider enabling parallel processing for better results"
            )
        
        if any(data['metrics']['avg_processing_time'] > 30 for data in stats['engines'].values()):
            recommendations['optimization_suggestions'].append(
                "Some engines are slow - consider adjusting timeout settings"
            )
        
        return recommendations
    
    def _try_get_from_cache(self, file_path: Path, options: OCROptions) -> Optional[OCRResult]:
        """Tentar obter resultado do cache."""
        try:
            # Preparar opções para cache
            cache_options = {
                'language': options.language,
                'confidence_threshold': options.confidence_threshold,
                'preprocessing': options.preprocessing,
                'dpi': options.dpi
            }
            
            # Buscar no cache
            cached_data = self.cache_manager.get_cached_result(file_path, cache_options)
            
            if cached_data:
                # Converter dados do cache para OCRResult
                result = self._convert_cache_to_ocr_result(cached_data, file_path, options)
                
                if result:
                    self.logger.info(f"💾 Cache hit: {file_path.name} "
                                   f"(engine: {result.engine}, confidence: {result.confidence:.2f})")
                    
                    # Atualizar estatísticas como se tivesse processado
                    self.total_processed += 1
                    self.total_success += 1
                    
                    return result
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Erro ao acessar cache: {e}")
            return None
    
    def _save_to_cache(self, file_path: Path, result: OCRResult, options: OCROptions):
        """Salvar resultado no cache."""
        try:
            # Converter OCRResult para formato de cache
            cache_data = self._convert_ocr_result_to_cache(result)
            
            # Preparar opções para cache
            cache_options = {
                'language': options.language,
                'confidence_threshold': options.confidence_threshold,
                'preprocessing': options.preprocessing,
                'dpi': options.dpi
            }
            
            # Salvar no cache
            success = self.cache_manager.save_result(
                file_path, cache_data, cache_options, result.engine
            )
            
            if success:
                self.logger.info(f"💾 Resultado salvo no cache: {file_path.name}")
            
        except Exception as e:
            self.logger.warning(f"Erro ao salvar no cache: {e}")
    
    def _convert_cache_to_ocr_result(self, cache_data: Dict, file_path: Path, 
                                   options: OCROptions) -> Optional[OCRResult]:
        """Converter dados do cache para OCRResult."""
        try:
            # Extrair metadados
            metadata = cache_data.get('metadata', {})
            pages_data = cache_data.get('pages', [])
            
            # Extrair texto completo
            full_text = '\n\n'.join([page.get('text', '') for page in pages_data])
            
            # Calcular métricas
            word_count = sum(len(page.get('text', '').split()) for page in pages_data)
            character_count = len(full_text)
            confidence = metadata.get('average_confidence', 0.0)
            processing_time = metadata.get('processing_time', 0.0)
            engine = metadata.get('method', 'cached')
            
            # Limpar nome do engine se necessário
            if '_' in engine:
                engine_parts = engine.split('_')
                if len(engine_parts) > 1:
                    engine = '_'.join(engine_parts[1:])  # Remove prefixos como "multi_engine"
            
            return OCRResult(
                text=full_text,
                confidence=confidence,
                pages=pages_data,
                processing_time=processing_time,
                engine=engine,
                language=options.language,
                file_path=str(file_path),
                word_count=word_count,
                character_count=character_count,
                success=True
            )
            
        except Exception as e:
            self.logger.error(f"Erro ao converter cache para OCRResult: {e}")
            return None
    
    def _convert_ocr_result_to_cache(self, result: OCRResult) -> Dict:
        """Converter OCRResult para formato de cache."""
        return {
            'pages': result.pages,
            'metadata': {
                'total_pages': len(result.pages),
                'processing_time': result.processing_time,
                'method': f"multi_engine_{result.engine}",
                'language': result.language,
                'average_confidence': result.confidence,
                'engine_used': result.engine,
                'word_count': result.word_count,
                'character_count': result.character_count
            },
            'success': result.success
        }
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Obter estatísticas do cache."""
        if not self.cache_manager:
            return {'cache_enabled': False}
        
        try:
            stats = self.cache_manager.get_cache_stats()
            stats['cache_enabled'] = True
            return stats
        except Exception as e:
            self.logger.error(f"Erro ao obter estatísticas do cache: {e}")
            return {'cache_enabled': True, 'error': str(e)}
    
    def cleanup_cache(self) -> int:
        """Limpar cache antigo."""
        if not self.cache_manager:
            return 0
        
        try:
            return self.cache_manager.cleanup_old_entries()
        except Exception as e:
            self.logger.error(f"Erro ao limpar cache: {e}")
            return 0
    
    def clear_cache(self) -> bool:
        """Limpar todo o cache."""
        if not self.cache_manager:
            return False
        
        try:
            return self.cache_manager.clear_cache()
        except Exception as e:
            self.logger.error(f"Erro ao limpar cache: {e}")
            return False


# Factory functions
def create_multi_engine_ocr(preferences: Optional[EnginePreferences] = None,
                           enable_cache: bool = True,
                           cache_dir: Optional[str] = None) -> MultiEngineOCR:
    """Factory function to create multi-engine OCR system with cache."""
    return MultiEngineOCR(preferences, enable_cache, cache_dir)


def setup_standard_engines(multi_ocr: MultiEngineOCR, 
                          azure_config: Optional[Dict] = None,
                          google_config: Optional[Dict] = None,
                          tesseract_config: Optional[Dict] = None,
                          mistral_config: Optional[Dict] = None) -> MultiEngineOCR:
    """
    Setup standard OCR engines in the multi-engine system.
    
    Args:
        multi_ocr: Multi-engine OCR instance
        azure_config: Azure Computer Vision configuration
        google_config: Google Cloud Vision configuration  
        tesseract_config: Tesseract configuration
        mistral_config: Mistral AI configuration
        
    Returns:
        Configured multi-engine OCR system
    """
    
    # Tesseract (local)
    if tesseract_config is not None:
        try:
            from .tesseract_engine import create_tesseract_engine
            tesseract = create_tesseract_engine(**tesseract_config)
            multi_ocr.register_engine(tesseract)
        except ImportError:
            pass
    
    # Azure Computer Vision
    if azure_config:
        try:
            from .azure_vision import create_azure_vision_engine
            azure = create_azure_vision_engine(**azure_config)
            multi_ocr.register_engine(azure)
        except ImportError:
            pass
    
    # Google Cloud Vision
    if google_config:
        try:
            from .google_vision import create_google_vision_engine
            google = create_google_vision_engine(**google_config)
            multi_ocr.register_engine(google)
        except ImportError:
            pass
    
    # Mistral AI
    if mistral_config:
        try:
            from .mistral_engine import create_mistral_engine
            mistral = create_mistral_engine(**mistral_config)
            multi_ocr.register_engine(mistral)
        except ImportError:
            pass
    
    return multi_ocr


# Example usage and testing
if __name__ == "__main__":
    from .base import OCROptions
    
    # Create preferences
    preferences = EnginePreferences(
        quality_threshold=0.8,
        enable_parallel_processing=True,
        enable_quality_comparison=True
    )
    
    # Create multi-engine system
    multi_ocr = create_multi_engine_ocr(preferences)
    
    print("Multi-Engine OCR System")
    print("=" * 40)
    print(f"Available engines: {multi_ocr.engine_manager.get_available_engines()}")
    print(f"Parallel processing: {preferences.enable_parallel_processing}")
    print(f"Quality threshold: {preferences.quality_threshold}")
    
    # Example configuration for engines
    example_configs = {
        'azure_config': {
            'endpoint': 'https://your-resource.cognitiveservices.azure.com/',
            'subscription_key': 'your-key-here'
        },
        'google_config': {
            'credentials_path': '/path/to/service-account.json'
        },
        'tesseract_config': {
            'tesseract_cmd': 'tesseract'
        }
    }
    
    print("\nExample engine configurations:")
    for engine, config in example_configs.items():
        print(f"  {engine}: {config}")
    
    print(f"\nTo use this system:")
    print("1. Configure your engine credentials")
    print("2. Call setup_standard_engines() with your configs")
    print("3. Use multi_ocr.process_file() to process documents")