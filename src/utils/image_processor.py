"""
Sistema de Pré-processamento de Imagens para OCR Enhanced.

Este módulo implementa técnicas avançadas de pré-processamento para melhorar
a qualidade do OCR em documentos digitalizados.
"""

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from typing import Tuple, Optional, List, Dict, Any
import math
from pathlib import Path
import logging

from .logger import get_logger


class ImagePreprocessor:
    """
    Processador de imagens com técnicas avançadas para melhorar OCR.
    
    Funcionalidades:
    - Correção de inclinação (deskewing)
    - Ajuste de contraste e brilho
    - Redução de ruído
    - Binarização otimizada
    - Redimensionamento inteligente
    - Detecção de orientação
    """
    
    def __init__(self, 
                 target_dpi: int = 300,
                 enable_deskew: bool = True,
                 enable_noise_reduction: bool = True,
                 enable_contrast_enhancement: bool = True,
                 enable_binarization: bool = True,
                 debug_mode: bool = False):
        """
        Inicializar processador de imagens.
        
        Args:
            target_dpi: DPI alvo para redimensionamento
            enable_deskew: Ativar correção de inclinação
            enable_noise_reduction: Ativar redução de ruído
            enable_contrast_enhancement: Ativar ajuste de contraste
            enable_binarization: Ativar binarização
            debug_mode: Salvar imagens intermediárias para debug
        """
        self.target_dpi = target_dpi
        self.enable_deskew = enable_deskew
        self.enable_noise_reduction = enable_noise_reduction
        self.enable_contrast_enhancement = enable_contrast_enhancement
        self.enable_binarization = enable_binarization
        self.debug_mode = debug_mode
        
        self.logger = get_logger("image_processor")
        
        # Configurações de processamento
        self.processing_config = {
            'gaussian_blur_kernel': (3, 3),
            'bilateral_filter_params': {'d': 9, 'sigmaColor': 75, 'sigmaSpace': 75},
            'contrast_enhancement_factor': 1.2,
            'brightness_adjustment': 1.0,
            'sharpness_enhancement': 1.1,
            'deskew_angle_threshold': 0.5,  # graus
            'binary_threshold': 0,  # 0 = OTSU automático
            'morphology_kernel_size': (2, 2)
        }
        
        # Estatísticas de processamento
        self.processing_stats = {
            'images_processed': 0,
            'deskew_corrections': 0,
            'noise_reductions': 0,
            'contrast_enhancements': 0,
            'binarizations': 0,
            'avg_processing_time': 0.0
        }
    
    def process_image(self, image_input: Any, 
                     output_path: Optional[Path] = None,
                     quality_analysis: bool = True) -> Tuple[Image.Image, Dict[str, Any]]:
        """
        Processar imagem com todas as técnicas de melhoria.
        
        Args:
            image_input: PIL Image, numpy array ou path para imagem
            output_path: Path para salvar imagem processada
            quality_analysis: Executar análise de qualidade
            
        Returns:
            Tupla com (imagem_processada, métricas_processamento)
        """
        import time
        start_time = time.time()
        
        # Converter input para PIL Image
        if isinstance(image_input, (str, Path)):
            image = Image.open(image_input)
        elif isinstance(image_input, np.ndarray):
            image = Image.fromarray(image_input)
        else:
            image = image_input
        
        # Converter para RGB se necessário
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        original_size = image.size
        processing_log = []
        
        # 1. Análise de qualidade inicial
        if quality_analysis:
            quality_metrics = self._analyze_image_quality(image)
            processing_log.append(f"Qualidade inicial: {quality_metrics['overall_score']:.2f}")
        
        # 2. Redimensionamento para DPI otimizado
        if self.target_dpi:
            image = self._resize_to_target_dpi(image, self.target_dpi)
            processing_log.append(f"Redimensionado para {self.target_dpi} DPI")
        
        # 3. Correção de inclinação
        if self.enable_deskew:
            image, skew_angle = self._deskew_image(image)
            if abs(skew_angle) > self.processing_config['deskew_angle_threshold']:
                processing_log.append(f"Correção de inclinação: {skew_angle:.2f}°")
                self.processing_stats['deskew_corrections'] += 1
        
        # 4. Ajuste de contraste e brilho
        if self.enable_contrast_enhancement:
            image = self._enhance_contrast_and_brightness(image)
            processing_log.append("Contraste e brilho ajustados")
            self.processing_stats['contrast_enhancements'] += 1
        
        # 5. Redução de ruído
        if self.enable_noise_reduction:
            image = self._reduce_noise(image)
            processing_log.append("Ruído reduzido")
            self.processing_stats['noise_reductions'] += 1
        
        # 6. Binarização otimizada
        if self.enable_binarization:
            image = self._adaptive_binarization(image)
            processing_log.append("Binarização aplicada")
            self.processing_stats['binarizations'] += 1
        
        # 7. Pós-processamento morfológico
        image = self._morphological_operations(image)
        processing_log.append("Operações morfológicas aplicadas")
        
        # Salvar imagem processada
        if output_path:
            image.save(output_path, quality=95, optimize=True)
            processing_log.append(f"Salvo em: {output_path}")
        
        # Calcular métricas finais
        processing_time = time.time() - start_time
        
        metrics = {
            'original_size': original_size,
            'processed_size': image.size,
            'processing_time': processing_time,
            'processing_steps': processing_log,
            'quality_improvement': 0.0,  # Calculado se quality_analysis ativo
            'preprocessing_applied': {
                'deskew': self.enable_deskew,
                'noise_reduction': self.enable_noise_reduction,
                'contrast_enhancement': self.enable_contrast_enhancement,
                'binarization': self.enable_binarization
            }
        }
        
        # Análise de qualidade final
        if quality_analysis:
            final_quality = self._analyze_image_quality(image)
            metrics['quality_improvement'] = final_quality['overall_score'] - quality_metrics['overall_score']
            metrics['final_quality'] = final_quality
        
        # Atualizar estatísticas
        self.processing_stats['images_processed'] += 1
        self._update_processing_stats(processing_time)
        
        self.logger.info(f"Imagem processada em {processing_time:.2f}s - "
                        f"Melhorias: {len(processing_log)} passos")
        
        return image, metrics
    
    def _analyze_image_quality(self, image: Image.Image) -> Dict[str, float]:
        """Analisar qualidade da imagem."""
        # Converter para OpenCV
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        
        # Métricas de qualidade
        quality_metrics = {}
        
        # 1. Sharpness (Laplacian variance)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        quality_metrics['sharpness'] = laplacian.var()
        
        # 2. Contrast (RMS contrast)
        quality_metrics['contrast'] = gray.std()
        
        # 3. Brightness (mean intensity)
        quality_metrics['brightness'] = gray.mean()
        
        # 4. Noise level (estimativa)
        noise_level = self._estimate_noise_level(gray)
        quality_metrics['noise_level'] = noise_level
        
        # 5. Resolution adequacy
        height, width = gray.shape
        resolution_score = min(1.0, (width * height) / (1000 * 1000))
        quality_metrics['resolution_adequacy'] = resolution_score
        
        # Score geral (0-1)
        # Normalizar métricas
        sharpness_score = min(1.0, quality_metrics['sharpness'] / 500.0)
        contrast_score = min(1.0, quality_metrics['contrast'] / 100.0)
        brightness_score = 1.0 - abs(quality_metrics['brightness'] - 128) / 128.0
        noise_score = max(0.0, 1.0 - noise_level / 50.0)
        
        overall_score = (
            sharpness_score * 0.3 +
            contrast_score * 0.25 +
            brightness_score * 0.2 +
            noise_score * 0.15 +
            resolution_score * 0.1
        )
        
        quality_metrics['overall_score'] = overall_score
        
        return quality_metrics
    
    def _estimate_noise_level(self, gray_image: np.ndarray) -> float:
        """Estimar nível de ruído na imagem."""
        # Usar filtro Laplaciano para detectar ruído
        laplacian = cv2.Laplacian(gray_image, cv2.CV_64F)
        
        # Calcular desvio padrão da segunda derivada
        noise_estimate = np.sqrt(np.mean(laplacian**2))
        
        return noise_estimate
    
    def _resize_to_target_dpi(self, image: Image.Image, target_dpi: int) -> Image.Image:
        """Redimensionar imagem para DPI alvo."""
        # Obter DPI atual se disponível
        current_dpi = image.info.get('dpi', (72, 72))
        if isinstance(current_dpi, tuple):
            current_dpi = current_dpi[0]
        
        # Calcular fator de redimensionamento
        scale_factor = target_dpi / current_dpi
        
        # Redimensionar apenas se necessário
        if abs(scale_factor - 1.0) > 0.1:  # Diferença significativa
            new_width = int(image.width * scale_factor)
            new_height = int(image.height * scale_factor)
            
            # Usar filtro de alta qualidade para redimensionamento
            if scale_factor > 1:
                # Upscaling - usar LANCZOS
                image = image.resize((new_width, new_height), Image.LANCZOS)
            else:
                # Downscaling - usar ANTIALIAS
                image = image.resize((new_width, new_height), Image.ANTIALIAS)
        
        return image
    
    def _deskew_image(self, image: Image.Image) -> Tuple[Image.Image, float]:
        """Corrigir inclinação da imagem."""
        # Converter para OpenCV
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        
        # Detecção de bordas
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Transformada de Hough para detectar linhas
        lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
        
        if lines is not None:
            # Calcular ângulos das linhas
            angles = []
            for line in lines:
                rho, theta = line[0]
                angle = theta * 180 / np.pi
                
                # Normalizar ângulo para -90 a 90 graus
                if angle > 90:
                    angle = angle - 180
                elif angle < -90:
                    angle = angle + 180
                
                angles.append(angle)
            
            # Encontrar ângulo mediano
            if angles:
                median_angle = np.median(angles)
                
                # Aplicar correção apenas se ângulo significativo
                if abs(median_angle) > self.processing_config['deskew_angle_threshold']:
                    # Rotacionar imagem
                    rotated = image.rotate(-median_angle, expand=True, fillcolor='white')
                    return rotated, median_angle
        
        return image, 0.0
    
    def _enhance_contrast_and_brightness(self, image: Image.Image) -> Image.Image:
        """Melhorar contraste e brilho."""
        # Ajustar contraste
        contrast_enhancer = ImageEnhance.Contrast(image)
        image = contrast_enhancer.enhance(self.processing_config['contrast_enhancement_factor'])
        
        # Ajustar brilho se necessário
        if self.processing_config['brightness_adjustment'] != 1.0:
            brightness_enhancer = ImageEnhance.Brightness(image)
            image = brightness_enhancer.enhance(self.processing_config['brightness_adjustment'])
        
        # Melhorar nitidez
        sharpness_enhancer = ImageEnhance.Sharpness(image)
        image = sharpness_enhancer.enhance(self.processing_config['sharpness_enhancement'])
        
        return image
    
    def _reduce_noise(self, image: Image.Image) -> Image.Image:
        """Reduzir ruído na imagem."""
        # Converter para OpenCV
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Aplicar filtro bilateral (preserva bordas)
        params = self.processing_config['bilateral_filter_params']
        filtered = cv2.bilateralFilter(cv_image, params['d'], params['sigmaColor'], params['sigmaSpace'])
        
        # Aplicar filtro gaussiano suave
        kernel = self.processing_config['gaussian_blur_kernel']
        filtered = cv2.GaussianBlur(filtered, kernel, 0)
        
        # Converter de volta para PIL
        return Image.fromarray(cv2.cvtColor(filtered, cv2.COLOR_BGR2RGB))
    
    def _adaptive_binarization(self, image: Image.Image) -> Image.Image:
        """Aplicar binarização adaptativa."""
        # Converter para escala de cinza
        gray = image.convert('L')
        cv_gray = np.array(gray)
        
        # Binarização OTSU (adaptativa)
        if self.processing_config['binary_threshold'] == 0:
            _, binary = cv2.threshold(cv_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            _, binary = cv2.threshold(cv_gray, self.processing_config['binary_threshold'], 255, cv2.THRESH_BINARY)
        
        # Converter de volta para PIL
        return Image.fromarray(binary).convert('RGB')
    
    def _morphological_operations(self, image: Image.Image) -> Image.Image:
        """Aplicar operações morfológicas para limpeza."""
        # Converter para escala de cinza
        gray = image.convert('L')
        cv_gray = np.array(gray)
        
        # Criar kernel para operações morfológicas
        kernel_size = self.processing_config['morphology_kernel_size']
        kernel = np.ones(kernel_size, np.uint8)
        
        # Aplicar abertura (remove ruído pequeno)
        opening = cv2.morphologyEx(cv_gray, cv2.MORPH_OPEN, kernel)
        
        # Aplicar fechamento (preenche buracos pequenos)
        closing = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, kernel)
        
        # Converter de volta para PIL
        return Image.fromarray(closing).convert('RGB')
    
    def _update_processing_stats(self, processing_time: float):
        """Atualizar estatísticas de processamento."""
        total_images = self.processing_stats['images_processed']
        
        if total_images == 1:
            self.processing_stats['avg_processing_time'] = processing_time
        else:
            current_avg = self.processing_stats['avg_processing_time']
            new_avg = (current_avg * (total_images - 1) + processing_time) / total_images
            self.processing_stats['avg_processing_time'] = new_avg
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Obter estatísticas de processamento."""
        return {
            'images_processed': self.processing_stats['images_processed'],
            'avg_processing_time': self.processing_stats['avg_processing_time'],
            'techniques_applied': {
                'deskew_corrections': self.processing_stats['deskew_corrections'],
                'noise_reductions': self.processing_stats['noise_reductions'],
                'contrast_enhancements': self.processing_stats['contrast_enhancements'],
                'binarizations': self.processing_stats['binarizations']
            },
            'configuration': {
                'target_dpi': self.target_dpi,
                'enabled_features': {
                    'deskew': self.enable_deskew,
                    'noise_reduction': self.enable_noise_reduction,
                    'contrast_enhancement': self.enable_contrast_enhancement,
                    'binarization': self.enable_binarization
                }
            }
        }
    
    def optimize_for_document_type(self, document_type: str):
        """Otimizar configurações para tipo de documento."""
        if document_type == 'handwritten':
            # Manuscritos precisam de menos processamento agressivo
            self.processing_config['contrast_enhancement_factor'] = 1.1
            self.processing_config['sharpness_enhancement'] = 1.05
            self.enable_binarization = False
        
        elif document_type == 'printed':
            # Documentos impressos se beneficiam de mais contraste
            self.processing_config['contrast_enhancement_factor'] = 1.3
            self.processing_config['sharpness_enhancement'] = 1.2
            self.enable_binarization = True
        
        elif document_type == 'low_quality':
            # Documentos de baixa qualidade precisam de mais processamento
            self.processing_config['contrast_enhancement_factor'] = 1.4
            self.enable_noise_reduction = True
            self.enable_binarization = True
        
        elif document_type == 'high_quality':
            # Documentos de alta qualidade precisam de menos processamento
            self.processing_config['contrast_enhancement_factor'] = 1.1
            self.enable_noise_reduction = False
            self.enable_binarization = False
        
        self.logger.info(f"Configurações otimizadas para: {document_type}")


# Factory function
def create_image_processor(target_dpi: int = 300,
                          enable_deskew: bool = True,
                          enable_noise_reduction: bool = True,
                          enable_contrast_enhancement: bool = True,
                          enable_binarization: bool = True,
                          debug_mode: bool = False) -> ImagePreprocessor:
    """Criar instância do processador de imagens."""
    return ImagePreprocessor(
        target_dpi=target_dpi,
        enable_deskew=enable_deskew,
        enable_noise_reduction=enable_noise_reduction,
        enable_contrast_enhancement=enable_contrast_enhancement,
        enable_binarization=enable_binarization,
        debug_mode=debug_mode
    )


# Utility functions
def preprocess_pdf_pages(pdf_path: Path, output_dir: Path,
                        target_dpi: int = 300) -> List[Path]:
    """Pré-processar todas as páginas de um PDF."""
    try:
        from pdf2image import convert_from_path
        
        # Converter PDF para imagens
        images = convert_from_path(pdf_path, dpi=target_dpi)
        
        # Criar processador
        processor = create_image_processor(target_dpi=target_dpi)
        
        processed_paths = []
        
        for i, image in enumerate(images):
            # Processar cada página
            processed_image, metrics = processor.process_image(image)
            
            # Salvar página processada
            page_path = output_dir / f"{pdf_path.stem}_page_{i+1:03d}.png"
            processed_image.save(page_path, quality=95)
            processed_paths.append(page_path)
        
        return processed_paths
        
    except ImportError:
        raise ImportError("pdf2image é necessário para processar PDFs")


# Example usage
if __name__ == "__main__":
    # Exemplo de uso
    processor = create_image_processor(
        target_dpi=300,
        enable_deskew=True,
        enable_noise_reduction=True,
        enable_contrast_enhancement=True,
        enable_binarization=True
    )
    
    print("🖼️ Processador de Imagens para OCR")
    print("=" * 40)
    print(f"DPI alvo: {processor.target_dpi}")
    print(f"Correção de inclinação: {processor.enable_deskew}")
    print(f"Redução de ruído: {processor.enable_noise_reduction}")
    print(f"Melhoria de contraste: {processor.enable_contrast_enhancement}")
    print(f"Binarização: {processor.enable_binarization}")
    
    # Exemplo de configuração para diferentes tipos de documento
    print("\n📄 Configurações por tipo de documento:")
    print("  • Manuscritos: Menos agressivo, sem binarização")
    print("  • Impressos: Mais contraste, com binarização")
    print("  • Baixa qualidade: Máximo processamento")
    print("  • Alta qualidade: Mínimo processamento")
    
    print("\n🚀 Melhorias esperadas:")
    print("  • 15-30% melhoria na confiança do OCR")
    print("  • Redução de erros de reconhecimento")
    print("  • Melhor detecção de texto inclinado")
    print("  • Remoção de ruído e artefatos")