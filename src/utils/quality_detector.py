"""
Sistema de Detecção Automática de Qualidade de Imagem.

Este módulo implementa detecção automática de qualidade para otimizar
o processamento de OCR com base nas características da imagem.
"""

import cv2
import numpy as np
from PIL import Image
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import math

from .logger import get_logger


class ImageQuality(Enum):
    """Níveis de qualidade da imagem."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    VERY_POOR = "very_poor"


class DocumentType(Enum):
    """Tipos de documento detectados."""
    PRINTED = "printed"
    HANDWRITTEN = "handwritten"
    MIXED = "mixed"
    FORM = "form"
    TABLE = "table"
    UNKNOWN = "unknown"


@dataclass
class QualityMetrics:
    """Métricas de qualidade da imagem."""
    
    # Métricas básicas
    resolution: Tuple[int, int]
    dpi: Optional[int]
    file_size: Optional[int]
    
    # Métricas de qualidade
    sharpness_score: float
    contrast_score: float
    brightness_score: float
    noise_level: float
    
    # Métricas de conteúdo
    text_density: float
    edge_density: float
    white_space_ratio: float
    
    # Métricas de orientação
    skew_angle: float
    rotation_needed: bool
    
    # Classificações
    overall_quality: ImageQuality
    document_type: DocumentType
    
    # Recomendações
    recommended_dpi: int
    preprocessing_needed: List[str]
    ocr_engine_suggestion: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Converter para dicionário."""
        return {
            'resolution': self.resolution,
            'dpi': self.dpi,
            'file_size': self.file_size,
            'sharpness_score': self.sharpness_score,
            'contrast_score': self.contrast_score,
            'brightness_score': self.brightness_score,
            'noise_level': self.noise_level,
            'text_density': self.text_density,
            'edge_density': self.edge_density,
            'white_space_ratio': self.white_space_ratio,
            'skew_angle': self.skew_angle,
            'rotation_needed': self.rotation_needed,
            'overall_quality': self.overall_quality.value,
            'document_type': self.document_type.value,
            'recommended_dpi': self.recommended_dpi,
            'preprocessing_needed': self.preprocessing_needed,
            'ocr_engine_suggestion': self.ocr_engine_suggestion
        }


class ImageQualityDetector:
    """
    Detector automático de qualidade de imagem para OCR.
    
    Analisa imagens e fornece recomendações para otimização do OCR.
    """
    
    def __init__(self):
        """Inicializar detector de qualidade."""
        self.logger = get_logger("quality_detector")
        
        # Thresholds para classificação
        self.quality_thresholds = {
            'sharpness': {'excellent': 1000, 'good': 500, 'fair': 200, 'poor': 100},
            'contrast': {'excellent': 80, 'good': 60, 'fair': 40, 'poor': 20},
            'brightness': {'optimal_min': 80, 'optimal_max': 180},
            'noise': {'excellent': 10, 'good': 20, 'fair': 35, 'poor': 50},
            'resolution': {'min_width': 800, 'min_height': 600, 'optimal_dpi': 300}
        }
        
        # Configurações de detecção
        self.detection_config = {
            'edge_detection_params': {'low_threshold': 50, 'high_threshold': 150},
            'text_detection_params': {'min_area': 100, 'aspect_ratio_range': (0.1, 10)},
            'skew_detection_params': {'hough_threshold': 100, 'angle_tolerance': 1.0},
            'noise_estimation_method': 'laplacian_variance'
        }
        
        # Estatísticas
        self.analysis_stats = {
            'images_analyzed': 0,
            'quality_distribution': {q.value: 0 for q in ImageQuality},
            'document_type_distribution': {d.value: 0 for d in DocumentType},
            'avg_analysis_time': 0.0
        }
    
    def analyze_image(self, image_input: Any, 
                     file_path: Optional[Path] = None) -> QualityMetrics:
        """
        Analisar qualidade da imagem e gerar recomendações.
        
        Args:
            image_input: PIL Image, numpy array ou path para imagem
            file_path: Path do arquivo (para obter tamanho)
            
        Returns:
            Métricas de qualidade e recomendações
        """
        import time
        start_time = time.time()
        
        # Converter input para PIL Image
        if isinstance(image_input, (str, Path)):
            image_path = Path(image_input)
            image = Image.open(image_path)
            file_path = image_path
        elif isinstance(image_input, np.ndarray):
            image = Image.fromarray(image_input)
        else:
            image = image_input
        
        # Converter para RGB se necessário
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Obter informações básicas
        resolution = image.size
        dpi = self._extract_dpi(image)
        file_size = file_path.stat().st_size if file_path and file_path.exists() else None
        
        # Converter para OpenCV para análises avançadas
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        
        # Análises de qualidade
        sharpness_score = self._calculate_sharpness(gray)
        contrast_score = self._calculate_contrast(gray)
        brightness_score = self._calculate_brightness(gray)
        noise_level = self._estimate_noise_level(gray)
        
        # Análises de conteúdo
        text_density = self._calculate_text_density(gray)
        edge_density = self._calculate_edge_density(gray)
        white_space_ratio = self._calculate_white_space_ratio(gray)
        
        # Análises de orientação
        skew_angle = self._detect_skew_angle(gray)
        rotation_needed = abs(skew_angle) > 1.0
        
        # Classificações
        overall_quality = self._classify_overall_quality(
            sharpness_score, contrast_score, brightness_score, noise_level, resolution
        )
        document_type = self._classify_document_type(
            text_density, edge_density, white_space_ratio, gray
        )
        
        # Recomendações
        recommended_dpi = self._recommend_dpi(resolution, dpi, overall_quality)
        preprocessing_needed = self._recommend_preprocessing(
            overall_quality, document_type, skew_angle, noise_level, contrast_score
        )
        ocr_engine_suggestion = self._suggest_ocr_engine(
            overall_quality, document_type, text_density
        )
        
        # Criar métricas
        metrics = QualityMetrics(
            resolution=resolution,
            dpi=dpi,
            file_size=file_size,
            sharpness_score=sharpness_score,
            contrast_score=contrast_score,
            brightness_score=brightness_score,
            noise_level=noise_level,
            text_density=text_density,
            edge_density=edge_density,
            white_space_ratio=white_space_ratio,
            skew_angle=skew_angle,
            rotation_needed=rotation_needed,
            overall_quality=overall_quality,
            document_type=document_type,
            recommended_dpi=recommended_dpi,
            preprocessing_needed=preprocessing_needed,
            ocr_engine_suggestion=ocr_engine_suggestion
        )
        
        # Atualizar estatísticas
        analysis_time = time.time() - start_time
        self._update_analysis_stats(overall_quality, document_type, analysis_time)
        
        self.logger.info(f"Análise completa - Qualidade: {overall_quality.value}, "
                        f"Tipo: {document_type.value}, Tempo: {analysis_time:.2f}s")
        
        return metrics
    
    def _extract_dpi(self, image: Image.Image) -> Optional[int]:
        """Extrair DPI da imagem."""
        dpi_info = image.info.get('dpi')
        if dpi_info:
            if isinstance(dpi_info, tuple):
                return int(dpi_info[0])
            return int(dpi_info)
        return None
    
    def _calculate_sharpness(self, gray: np.ndarray) -> float:
        """Calcular nitidez usando variância do Laplaciano."""
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        return laplacian.var()
    
    def _calculate_contrast(self, gray: np.ndarray) -> float:
        """Calcular contraste usando desvio padrão."""
        return float(np.std(gray))
    
    def _calculate_brightness(self, gray: np.ndarray) -> float:
        """Calcular brilho médio."""
        return float(np.mean(gray))
    
    def _estimate_noise_level(self, gray: np.ndarray) -> float:
        """Estimar nível de ruído."""
        if self.detection_config['noise_estimation_method'] == 'laplacian_variance':
            # Método baseado em variância do Laplaciano
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            return float(np.sqrt(np.mean(laplacian**2)))
        else:
            # Método alternativo baseado em filtro de mediana
            median_filtered = cv2.medianBlur(gray, 5)
            noise = cv2.absdiff(gray, median_filtered)
            return float(np.mean(noise))
    
    def _calculate_text_density(self, gray: np.ndarray) -> float:
        """Calcular densidade de texto na imagem."""
        # Usar MSER (Maximally Stable Extremal Regions) para detectar texto
        try:
            mser = cv2.MSER_create()
            regions, _ = mser.detectRegions(gray)
            
            total_area = gray.shape[0] * gray.shape[1]
            text_area = 0
            
            for region in regions:
                # Filtrar regiões por tamanho e proporção
                if len(region) > self.detection_config['text_detection_params']['min_area']:
                    text_area += len(region)
            
            return text_area / total_area
            
        except Exception:
            # Fallback: usar detecção de bordas
            edges = cv2.Canny(gray, 50, 150)
            return np.sum(edges > 0) / edges.size
    
    def _calculate_edge_density(self, gray: np.ndarray) -> float:
        """Calcular densidade de bordas."""
        params = self.detection_config['edge_detection_params']
        edges = cv2.Canny(gray, params['low_threshold'], params['high_threshold'])
        return np.sum(edges > 0) / edges.size
    
    def _calculate_white_space_ratio(self, gray: np.ndarray) -> float:
        """Calcular proporção de espaço em branco."""
        # Threshold para considerar como "branco"
        white_threshold = 240
        white_pixels = np.sum(gray > white_threshold)
        total_pixels = gray.shape[0] * gray.shape[1]
        return white_pixels / total_pixels
    
    def _detect_skew_angle(self, gray: np.ndarray) -> float:
        """Detectar ângulo de inclinação."""
        # Detecção de bordas
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Transformada de Hough para detectar linhas
        params = self.detection_config['skew_detection_params']
        lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=params['hough_threshold'])
        
        if lines is not None:
            angles = []
            for line in lines:
                rho, theta = line[0]
                angle = theta * 180 / np.pi
                
                # Normalizar ângulo
                if angle > 90:
                    angle = angle - 180
                elif angle < -90:
                    angle = angle + 180
                
                # Filtrar ângulos próximos de horizontal
                if abs(angle) < 45:
                    angles.append(angle)
            
            if angles:
                return float(np.median(angles))
        
        return 0.0
    
    def _classify_overall_quality(self, sharpness: float, contrast: float, 
                                brightness: float, noise: float, 
                                resolution: Tuple[int, int]) -> ImageQuality:
        """Classificar qualidade geral da imagem."""
        # Calcular scores normalizados
        sharpness_score = self._normalize_score(sharpness, self.quality_thresholds['sharpness'])
        contrast_score = self._normalize_score(contrast, self.quality_thresholds['contrast'])
        
        # Score de brilho (otimizado para OCR)
        brightness_optimal = self.quality_thresholds['brightness']
        brightness_score = 1.0 - abs(brightness - 128) / 128.0
        
        # Score de ruído (invertido - menos ruído = melhor)
        noise_thresholds = self.quality_thresholds['noise']
        if noise < noise_thresholds['excellent']:
            noise_score = 1.0
        elif noise < noise_thresholds['good']:
            noise_score = 0.8
        elif noise < noise_thresholds['fair']:
            noise_score = 0.6
        elif noise < noise_thresholds['poor']:
            noise_score = 0.4
        else:
            noise_score = 0.2
        
        # Score de resolução
        width, height = resolution
        res_threshold = self.quality_thresholds['resolution']
        resolution_score = min(1.0, (width * height) / (res_threshold['min_width'] * res_threshold['min_height']))
        
        # Score combinado
        overall_score = (
            sharpness_score * 0.3 +
            contrast_score * 0.25 +
            brightness_score * 0.2 +
            noise_score * 0.15 +
            resolution_score * 0.1
        )
        
        # Classificar
        if overall_score >= 0.8:
            return ImageQuality.EXCELLENT
        elif overall_score >= 0.6:
            return ImageQuality.GOOD
        elif overall_score >= 0.4:
            return ImageQuality.FAIR
        elif overall_score >= 0.2:
            return ImageQuality.POOR
        else:
            return ImageQuality.VERY_POOR
    
    def _normalize_score(self, value: float, thresholds: Dict[str, float]) -> float:
        """Normalizar valor baseado em thresholds."""
        if value >= thresholds['excellent']:
            return 1.0
        elif value >= thresholds['good']:
            return 0.8
        elif value >= thresholds['fair']:
            return 0.6
        elif value >= thresholds['poor']:
            return 0.4
        else:
            return 0.2
    
    def _classify_document_type(self, text_density: float, edge_density: float,
                              white_space_ratio: float, gray: np.ndarray) -> DocumentType:
        """Classificar tipo de documento."""
        # Detectar contornos para análise de estrutura
        contours, _ = cv2.findContours(
            cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
            cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        # Analisar contornos
        rectangular_contours = 0
        total_contours = len(contours)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 500:  # Filtrar contornos pequenos
                # Aproximar contorno
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # Verificar se é retangular
                if len(approx) == 4:
                    rectangular_contours += 1
        
        # Calcular proporção de estruturas retangulares
        rect_ratio = rectangular_contours / max(1, total_contours)
        
        # Classificar baseado em características
        if rect_ratio > 0.3 and white_space_ratio > 0.7:
            return DocumentType.FORM
        elif rect_ratio > 0.4 and text_density < 0.3:
            return DocumentType.TABLE
        elif text_density > 0.4 and edge_density > 0.1:
            return DocumentType.PRINTED
        elif text_density > 0.2 and edge_density < 0.05:
            return DocumentType.HANDWRITTEN
        elif text_density > 0.3:
            return DocumentType.MIXED
        else:
            return DocumentType.UNKNOWN
    
    def _recommend_dpi(self, resolution: Tuple[int, int], 
                      current_dpi: Optional[int], 
                      quality: ImageQuality) -> int:
        """Recomendar DPI ideal."""
        width, height = resolution
        
        # DPI baseado na qualidade
        if quality == ImageQuality.EXCELLENT:
            base_dpi = 300
        elif quality == ImageQuality.GOOD:
            base_dpi = 300
        elif quality == ImageQuality.FAIR:
            base_dpi = 400
        elif quality == ImageQuality.POOR:
            base_dpi = 500
        else:
            base_dpi = 600
        
        # Ajustar baseado na resolução atual
        if current_dpi:
            if current_dpi < 150:
                return max(base_dpi, 400)
            elif current_dpi > 600:
                return min(base_dpi, 400)
        
        # Ajustar baseado na resolução
        if width < 1000 or height < 800:
            return max(base_dpi, 400)
        
        return base_dpi
    
    def _recommend_preprocessing(self, quality: ImageQuality, 
                               document_type: DocumentType,
                               skew_angle: float, noise_level: float,
                               contrast: float) -> List[str]:
        """Recomendar técnicas de pré-processamento."""
        recommendations = []
        
        # Correção de inclinação
        if abs(skew_angle) > 1.0:
            recommendations.append("deskew")
        
        # Redução de ruído
        if noise_level > self.quality_thresholds['noise']['good']:
            recommendations.append("noise_reduction")
        
        # Melhoria de contraste
        if contrast < self.quality_thresholds['contrast']['good']:
            recommendations.append("contrast_enhancement")
        
        # Binarização
        if quality in [ImageQuality.POOR, ImageQuality.VERY_POOR]:
            recommendations.append("binarization")
        
        # Nitidez
        if quality == ImageQuality.VERY_POOR:
            recommendations.append("sharpening")
        
        # Específico por tipo de documento
        if document_type == DocumentType.HANDWRITTEN:
            recommendations.append("gentle_processing")
        elif document_type == DocumentType.FORM:
            recommendations.append("structure_preservation")
        elif document_type == DocumentType.TABLE:
            recommendations.append("line_enhancement")
        
        return recommendations
    
    def _suggest_ocr_engine(self, quality: ImageQuality, 
                           document_type: DocumentType,
                           text_density: float) -> str:
        """Sugerir engine OCR ideal."""
        # Baseado na qualidade
        if quality == ImageQuality.EXCELLENT:
            if document_type == DocumentType.PRINTED:
                return "tesseract_local"
            else:
                return "google_cloud"
        
        elif quality == ImageQuality.GOOD:
            if document_type == DocumentType.HANDWRITTEN:
                return "azure_cloud"
            else:
                return "tesseract_local"
        
        elif quality == ImageQuality.FAIR:
            return "azure_cloud"
        
        else:  # POOR or VERY_POOR
            return "google_cloud"
    
    def _update_analysis_stats(self, quality: ImageQuality, 
                             document_type: DocumentType, 
                             analysis_time: float):
        """Atualizar estatísticas de análise."""
        self.analysis_stats['images_analyzed'] += 1
        self.analysis_stats['quality_distribution'][quality.value] += 1
        self.analysis_stats['document_type_distribution'][document_type.value] += 1
        
        # Atualizar tempo médio
        total_images = self.analysis_stats['images_analyzed']
        if total_images == 1:
            self.analysis_stats['avg_analysis_time'] = analysis_time
        else:
            current_avg = self.analysis_stats['avg_analysis_time']
            new_avg = (current_avg * (total_images - 1) + analysis_time) / total_images
            self.analysis_stats['avg_analysis_time'] = new_avg
    
    def get_analysis_statistics(self) -> Dict[str, Any]:
        """Obter estatísticas de análise."""
        return {
            'images_analyzed': self.analysis_stats['images_analyzed'],
            'avg_analysis_time': self.analysis_stats['avg_analysis_time'],
            'quality_distribution': self.analysis_stats['quality_distribution'],
            'document_type_distribution': self.analysis_stats['document_type_distribution'],
            'thresholds': self.quality_thresholds
        }
    
    def generate_quality_report(self, metrics: QualityMetrics) -> str:
        """Gerar relatório de qualidade legível."""
        report = f"""
📊 RELATÓRIO DE QUALIDADE DA IMAGEM

📐 Informações Básicas:
   • Resolução: {metrics.resolution[0]}x{metrics.resolution[1]}
   • DPI: {metrics.dpi or 'Não detectado'}
   • Tamanho: {metrics.file_size/1024:.1f} KB" if metrics.file_size else 'Desconhecido'

🔍 Métricas de Qualidade:
   • Nitidez: {metrics.sharpness_score:.1f}
   • Contraste: {metrics.contrast_score:.1f}
   • Brilho: {metrics.brightness_score:.1f}
   • Ruído: {metrics.noise_level:.1f}

📄 Análise de Conteúdo:
   • Densidade de texto: {metrics.text_density:.2%}
   • Densidade de bordas: {metrics.edge_density:.2%}
   • Espaço em branco: {metrics.white_space_ratio:.2%}

🔄 Orientação:
   • Inclinação: {metrics.skew_angle:.1f}°
   • Rotação necessária: {'Sim' if metrics.rotation_needed else 'Não'}

🎯 Classificação:
   • Qualidade geral: {metrics.overall_quality.value.upper()}
   • Tipo de documento: {metrics.document_type.value.upper()}

💡 Recomendações:
   • DPI recomendado: {metrics.recommended_dpi}
   • Engine OCR sugerida: {metrics.ocr_engine_suggestion}
   • Pré-processamento: {', '.join(metrics.preprocessing_needed) if metrics.preprocessing_needed else 'Não necessário'}
"""
        return report


# Factory function
def create_quality_detector() -> ImageQualityDetector:
    """Criar instância do detector de qualidade."""
    return ImageQualityDetector()


# Example usage
if __name__ == "__main__":
    # Exemplo de uso
    detector = create_quality_detector()
    
    print("🔍 Detector de Qualidade de Imagem")
    print("=" * 40)
    print("Funcionalidades:")
    print("  • Análise automática de qualidade")
    print("  • Detecção de tipo de documento")
    print("  • Recomendações de pré-processamento")
    print("  • Sugestão de engine OCR")
    print("  • Otimização de DPI")
    
    print("\n📊 Métricas analisadas:")
    print("  • Nitidez (Laplacian variance)")
    print("  • Contraste (desvio padrão)")
    print("  • Brilho (intensidade média)")
    print("  • Ruído (estimativa)")
    print("  • Densidade de texto")
    print("  • Inclinação (Hough transform)")
    
    print("\n🎯 Classificações:")
    print("  • Qualidade: Excelente → Muito Ruim")
    print("  • Tipo: Impresso, Manuscrito, Formulário, Tabela")
    print("  • Recomendações personalizadas por tipo")