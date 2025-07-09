"""
Sistema de Pós-processamento de Texto para OCR Enhanced.

Este módulo implementa técnicas avançadas de pós-processamento para melhorar
a qualidade do texto extraído por OCR, incluindo correção ortográfica,
detecção de padrões e validação de consistência.
"""

import re
import unicodedata
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass
from pathlib import Path
import json
import statistics

from .logger import get_logger


@dataclass
class TextProcessingMetrics:
    """Métricas de processamento de texto."""
    
    original_length: int
    processed_length: int
    words_corrected: int
    patterns_detected: int
    confidence_improvement: float
    processing_time: float
    
    corrections_applied: List[str]
    patterns_found: Dict[str, List[str]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Converter para dicionário."""
        return {
            'original_length': self.original_length,
            'processed_length': self.processed_length,
            'words_corrected': self.words_corrected,
            'patterns_detected': self.patterns_detected,
            'confidence_improvement': self.confidence_improvement,
            'processing_time': self.processing_time,
            'corrections_applied': self.corrections_applied,
            'patterns_found': self.patterns_found
        }


class TextProcessor:
    """
    Processador de texto com técnicas avançadas de pós-processamento.
    
    Funcionalidades:
    - Correção ortográfica contextual
    - Detecção de padrões (CPF, CNPJ, datas, etc.)
    - Validação de consistência
    - Formatação inteligente
    - Limpeza de artefatos OCR
    """
    
    def __init__(self, language: str = "pt-BR"):
        """
        Inicializar processador de texto.
        
        Args:
            language: Idioma para processamento
        """
        self.language = language
        self.logger = get_logger("text_processor")
        
        # Carregar dicionários e padrões
        self.load_dictionaries()
        self.load_patterns()
        
        # Estatísticas
        self.processing_stats = {
            'texts_processed': 0,
            'total_corrections': 0,
            'total_patterns_found': 0,
            'avg_confidence_improvement': 0.0,
            'avg_processing_time': 0.0
        }
    
    def load_dictionaries(self):
        """Carregar dicionários de correção."""
        # Dicionário de palavras comuns em português
        self.common_words = {
            'o', 'a', 'de', 'que', 'e', 'do', 'da', 'em', 'um', 'para', 'é', 'com',
            'não', 'uma', 'os', 'no', 'se', 'na', 'por', 'mais', 'as', 'dos', 'como',
            'mas', 'foi', 'ao', 'ele', 'das', 'tem', 'à', 'seu', 'sua', 'ou', 'ser',
            'quando', 'muito', 'há', 'nos', 'já', 'está', 'eu', 'também', 'só', 'pelo',
            'pela', 'até', 'isso', 'ela', 'entre', 'era', 'depois', 'sem', 'mesmo',
            'aos', 'ter', 'seus', 'suas', 'numa', 'nem', 'suas', 'meu', 'às', 'minha',
            'têm', 'numa', 'pelos', 'pelas', 'só', 'nós', 'você', 'vocês', 'ele', 'ela',
            'eles', 'elas', 'esse', 'essa', 'esses', 'essas', 'aquele', 'aquela',
            'aqueles', 'aquelas', 'este', 'esta', 'estes', 'estas', 'outro', 'outra',
            'outros', 'outras', 'qual', 'quais', 'quanto', 'quantos', 'quanta', 'quantas'
        }
        
        # Correções comuns de OCR
        self.ocr_corrections = {
            # Substituições de caracteres confusos
            'rn': 'm',  # r+n confundido com m
            'cl': 'd',  # c+l confundido com d
            'li': 'h',  # l+i confundido com h
            'nn': 'n',  # n duplicado
            'oo': 'o',  # o duplicado
            'ii': 'i',  # i duplicado
            '0': 'o',   # zero confundido com o (em contexto)
            'O': '0',   # O confundido com zero (em contexto)
            'l': '1',   # l confundido com 1 (em contexto)
            'I': '1',   # I confundido com 1 (em contexto)
            'S': '5',   # S confundido com 5 (em contexto)
            'G': '6',   # G confundido com 6 (em contexto)
            'B': '8',   # B confundido com 8 (em contexto)
            'g': '9',   # g confundido com 9 (em contexto)
            
            # Correções de palavras específicas
            'voce': 'você',
            'nao': 'não',
            'estao': 'estão',
            'entao': 'então',
            'coracao': 'coração',
            'posicao': 'posição',
            'informacao': 'informação',
            'atencao': 'atenção',
            'funcao': 'função',
            'decisao': 'decisão',
            'opcao': 'opção',
            'situacao': 'situação',
            'condicao': 'condição'
        }
        
        # Abreviações comuns
        self.abbreviations = {
            'dr': 'Dr.',
            'dra': 'Dra.',
            'sr': 'Sr.',
            'sra': 'Sra.',
            'ltda': 'Ltda.',
            'sa': 'S.A.',
            'cia': 'Cia.',
            'prof': 'Prof.',
            'profa': 'Profa.',
            'av': 'Av.',
            'r': 'R.',
            'al': 'Al.',
            'tv': 'Tv.',
            'pca': 'Pça.',
            'est': 'Est.',
            'rod': 'Rod.',
            'km': 'Km.',
            'n': 'Nº',
            'art': 'Art.',
            'inc': 'Inc.',
            'par': 'Par.',
            'cf': 'Cf.',
            'fl': 'Fl.',
            'fls': 'Fls.',
            'p': 'P.',
            'pp': 'Pp.',
            'obs': 'Obs.',
            'ref': 'Ref.',
            'anexo': 'Anexo',
            'apendice': 'Apêndice'
        }
    
    def load_patterns(self):
        """Carregar padrões de detecção."""
        # Padrões de documentos brasileiros
        self.patterns = {
            'cpf': {
                'regex': r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b',
                'format': r'(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})',
                'formatter': r'\1.\2.\3-\4',
                'validator': self._validate_cpf
            },
            'cnpj': {
                'regex': r'\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b',
                'format': r'(\d{2})\.?(\d{3})\.?(\d{3})/(\d{4})-?(\d{2})',
                'formatter': r'\1.\2.\3/\4-\5',
                'validator': self._validate_cnpj
            },
            'cep': {
                'regex': r'\b\d{5}-?\d{3}\b',
                'format': r'(\d{5})-?(\d{3})',
                'formatter': r'\1-\2',
                'validator': None
            },
            'phone': {
                'regex': r'\b\(?\d{2}\)?\s?\d{4,5}-?\d{4}\b',
                'format': r'\(?(\d{2})\)?\s?(\d{4,5})-?(\d{4})',
                'formatter': r'(\1) \2-\3',
                'validator': None
            },
            'date': {
                'regex': r'\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b',
                'format': r'(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})',
                'formatter': r'\1/\2/\3',
                'validator': self._validate_date
            },
            'time': {
                'regex': r'\b\d{1,2}:\d{2}(:\d{2})?\b',
                'format': r'(\d{1,2}):(\d{2})(:\d{2})?',
                'formatter': r'\1:\2\3',
                'validator': self._validate_time
            },
            'currency': {
                'regex': r'R\$\s?\d{1,3}(?:\.\d{3})*(?:,\d{2})?',
                'format': r'R\$\s?(\d{1,3}(?:\.\d{3})*)(?:,(\d{2}))?',
                'formatter': r'R$ \1,\2',
                'validator': None
            },
            'email': {
                'regex': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                'format': None,
                'formatter': None,
                'validator': self._validate_email
            },
            'url': {
                'regex': r'https?://[^\s<>"{}|\\^`[\]]+',
                'format': None,
                'formatter': None,
                'validator': None
            },
            'processo_judicial': {
                'regex': r'\b\d{7}-?\d{2}\.\d{4}\.\d{1}\.\d{2}\.\d{4}\b',
                'format': r'(\d{7})-?(\d{2})\.(\d{4})\.(\d{1})\.(\d{2})\.(\d{4})',
                'formatter': r'\1-\2.\3.\4.\5.\6',
                'validator': None
            }
        }
    
    def process_text(self, text: str, confidence: float = 0.0) -> Tuple[str, TextProcessingMetrics]:
        """
        Processar texto com todas as técnicas de melhoria.
        
        Args:
            text: Texto original
            confidence: Confiança do OCR original
            
        Returns:
            Tupla com (texto_processado, métricas)
        """
        import time
        start_time = time.time()
        
        original_text = text
        original_length = len(text)
        
        corrections_applied = []
        patterns_found = {}
        
        # 1. Limpeza básica
        text = self._clean_text(text)
        if text != original_text:
            corrections_applied.append("limpeza_basica")
        
        # 2. Correção de caracteres confusos
        text, char_corrections = self._correct_confused_characters(text)
        if char_corrections > 0:
            corrections_applied.append(f"caracteres_confusos_{char_corrections}")
        
        # 3. Correção ortográfica
        text, word_corrections = self._correct_spelling(text)
        if word_corrections > 0:
            corrections_applied.append(f"correcao_ortografica_{word_corrections}")
        
        # 4. Detecção e formatação de padrões
        text, detected_patterns = self._detect_and_format_patterns(text)
        patterns_found = detected_patterns
        
        # 5. Correção de abreviações
        text, abbrev_corrections = self._correct_abbreviations(text)
        if abbrev_corrections > 0:
            corrections_applied.append(f"abreviacoes_{abbrev_corrections}")
        
        # 6. Formatação final
        text = self._format_text(text)
        corrections_applied.append("formatacao_final")
        
        # 7. Validação de consistência
        text = self._validate_consistency(text)
        corrections_applied.append("validacao_consistencia")
        
        # Calcular métricas
        processing_time = time.time() - start_time
        processed_length = len(text)
        total_corrections = char_corrections + word_corrections + abbrev_corrections
        patterns_detected = sum(len(patterns) for patterns in patterns_found.values())
        
        # Estimar melhoria na confiança
        confidence_improvement = self._estimate_confidence_improvement(
            original_text, text, total_corrections, patterns_detected
        )
        
        metrics = TextProcessingMetrics(
            original_length=original_length,
            processed_length=processed_length,
            words_corrected=total_corrections,
            patterns_detected=patterns_detected,
            confidence_improvement=confidence_improvement,
            processing_time=processing_time,
            corrections_applied=corrections_applied,
            patterns_found=patterns_found
        )
        
        # Atualizar estatísticas
        self._update_processing_stats(metrics)
        
        self.logger.info(f"Texto processado: {total_corrections} correções, "
                        f"{patterns_detected} padrões, +{confidence_improvement:.2f} confiança")
        
        return text, metrics
    
    def _clean_text(self, text: str) -> str:
        """Limpeza básica do texto."""
        # Remover caracteres de controle
        text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C' or char in '\n\t')
        
        # Normalizar espaços
        text = re.sub(r'\s+', ' ', text)
        
        # Remover espaços no início e fim
        text = text.strip()
        
        # Corrigir quebras de linha problemáticas
        text = re.sub(r'\n\s*\n', '\n\n', text)  # Múltiplas quebras
        text = re.sub(r'([a-z])\n([a-z])', r'\1 \2', text)  # Quebras no meio de palavras
        
        return text
    
    def _correct_confused_characters(self, text: str) -> Tuple[str, int]:
        """Corrigir caracteres confusos do OCR."""
        corrections = 0
        
        # Correções contextuais
        for wrong, correct in self.ocr_corrections.items():
            if len(wrong) == 1 and len(correct) == 1:
                # Correções de caracteres únicos precisam de contexto
                if wrong.isdigit() and correct.isalpha():
                    # Número para letra - só em contexto de palavra
                    pattern = r'\b\w*' + re.escape(wrong) + r'\w*\b'
                    matches = re.findall(pattern, text)
                    for match in matches:
                        if not match.isdigit():  # Não é só números
                            new_match = match.replace(wrong, correct)
                            text = text.replace(match, new_match)
                            corrections += 1
                
                elif wrong.isalpha() and correct.isdigit():
                    # Letra para número - só em contexto numérico
                    pattern = r'\b\d*' + re.escape(wrong) + r'\d*\b'
                    matches = re.findall(pattern, text)
                    for match in matches:
                        if not match.isalpha():  # Não é só letras
                            new_match = match.replace(wrong, correct)
                            text = text.replace(match, new_match)
                            corrections += 1
            else:
                # Correções de múltiplos caracteres
                if wrong in text:
                    text = text.replace(wrong, correct)
                    corrections += text.count(correct) - text.count(wrong)
        
        return text, corrections
    
    def _correct_spelling(self, text: str) -> Tuple[str, int]:
        """Correção ortográfica básica."""
        corrections = 0
        words = text.split()
        
        for i, word in enumerate(words):
            # Limpar palavra para análise
            clean_word = re.sub(r'[^\w]', '', word.lower())
            
            # Verificar se precisa de correção
            if clean_word in self.ocr_corrections:
                # Preservar capitalização e pontuação
                corrected = self._preserve_word_format(word, self.ocr_corrections[clean_word])
                if corrected != word:
                    words[i] = corrected
                    corrections += 1
        
        return ' '.join(words), corrections
    
    def _preserve_word_format(self, original: str, correction: str) -> str:
        """Preservar formatação original da palavra."""
        # Encontrar início e fim da palavra
        start_punct = re.match(r'^[^\w]*', original).group()
        end_punct = re.search(r'[^\w]*$', original).group()
        
        # Extrair palavra limpa
        clean_original = original[len(start_punct):len(original)-len(end_punct) if end_punct else len(original)]
        
        # Aplicar capitalização
        if clean_original.isupper():
            formatted_correction = correction.upper()
        elif clean_original.istitle():
            formatted_correction = correction.capitalize()
        else:
            formatted_correction = correction
        
        return start_punct + formatted_correction + end_punct
    
    def _detect_and_format_patterns(self, text: str) -> Tuple[str, Dict[str, List[str]]]:
        """Detectar e formatar padrões no texto."""
        patterns_found = {}
        
        for pattern_name, pattern_config in self.patterns.items():
            regex = pattern_config['regex']
            formatter = pattern_config.get('formatter')
            validator = pattern_config.get('validator')
            
            matches = re.findall(regex, text)
            if matches:
                patterns_found[pattern_name] = []
                
                for match in matches:
                    if isinstance(match, tuple):
                        match_str = ''.join(match)
                    else:
                        match_str = match
                    
                    # Validar se necessário
                    if validator and not validator(match_str):
                        continue
                    
                    # Formatar se necessário
                    if formatter and pattern_config.get('format'):
                        formatted = re.sub(pattern_config['format'], formatter, match_str)
                        text = text.replace(match_str, formatted)
                        patterns_found[pattern_name].append(formatted)
                    else:
                        patterns_found[pattern_name].append(match_str)
        
        return text, patterns_found
    
    def _correct_abbreviations(self, text: str) -> Tuple[str, int]:
        """Corrigir abreviações."""
        corrections = 0
        
        for abbrev, full_form in self.abbreviations.items():
            # Buscar abreviação no início de palavra ou após espaço
            pattern = r'\b' + re.escape(abbrev) + r'\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            
            for match in matches:
                # Preservar capitalização
                if match.isupper():
                    replacement = full_form.upper()
                elif match.istitle():
                    replacement = full_form
                else:
                    replacement = full_form.lower()
                
                text = re.sub(r'\b' + re.escape(match) + r'\b', replacement, text)
                corrections += 1
        
        return text, corrections
    
    def _format_text(self, text: str) -> str:
        """Formatação final do texto."""
        # Corrigir espaçamento em pontuação
        text = re.sub(r'\s+([.,;:!?])', r'\1', text)  # Remover espaço antes da pontuação
        text = re.sub(r'([.,;:!?])\s*', r'\1 ', text)  # Adicionar espaço após pontuação
        
        # Corrigir aspas
        text = re.sub(r'\s+"', r' "', text)
        text = re.sub(r'"\s+', r'" ', text)
        
        # Corrigir parênteses
        text = re.sub(r'\s+\(', r' (', text)
        text = re.sub(r'\(\s+', r'(', text)
        text = re.sub(r'\s+\)', r')', text)
        text = re.sub(r'\)\s+', r') ', text)
        
        # Normalizar espaços múltiplos
        text = re.sub(r'\s+', ' ', text)
        
        # Corrigir quebras de linha
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Máximo 2 quebras
        
        return text.strip()
    
    def _validate_consistency(self, text: str) -> str:
        """Validar consistência do texto."""
        lines = text.split('\n')
        
        # Verificar linhas muito curtas que podem ser artefatos
        filtered_lines = []
        for line in lines:
            line = line.strip()
            if len(line) > 2 or line in ['.', '!', '?', ':', ';']:
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
    
    def _estimate_confidence_improvement(self, original: str, processed: str, 
                                       corrections: int, patterns: int) -> float:
        """Estimar melhoria na confiança."""
        # Fatores de melhoria
        correction_factor = min(0.15, corrections * 0.02)  # Até 15% por correções
        pattern_factor = min(0.10, patterns * 0.05)       # Até 10% por padrões
        length_factor = min(0.05, abs(len(processed) - len(original)) / len(original))
        
        # Penalizar se texto ficou muito diferente
        if len(processed) < len(original) * 0.8:
            length_factor = -length_factor
        
        total_improvement = correction_factor + pattern_factor + length_factor
        return max(0.0, min(0.30, total_improvement))  # Máximo 30% de melhoria
    
    def _validate_cpf(self, cpf: str) -> bool:
        """Validar CPF."""
        # Remover formatação
        cpf = re.sub(r'[^\d]', '', cpf)
        
        if len(cpf) != 11 or cpf == cpf[0] * 11:
            return False
        
        # Calcular dígitos verificadores
        def calculate_digit(cpf_digits, weights):
            total = sum(int(digit) * weight for digit, weight in zip(cpf_digits, weights))
            remainder = total % 11
            return 0 if remainder < 2 else 11 - remainder
        
        # Primeiro dígito
        first_digit = calculate_digit(cpf[:9], range(10, 1, -1))
        if first_digit != int(cpf[9]):
            return False
        
        # Segundo dígito
        second_digit = calculate_digit(cpf[:10], range(11, 1, -1))
        if second_digit != int(cpf[10]):
            return False
        
        return True
    
    def _validate_cnpj(self, cnpj: str) -> bool:
        """Validar CNPJ."""
        # Remover formatação
        cnpj = re.sub(r'[^\d]', '', cnpj)
        
        if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
            return False
        
        # Calcular dígitos verificadores
        def calculate_digit(cnpj_digits, weights):
            total = sum(int(digit) * weight for digit, weight in zip(cnpj_digits, weights))
            remainder = total % 11
            return 0 if remainder < 2 else 11 - remainder
        
        # Primeiro dígito
        weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        first_digit = calculate_digit(cnpj[:12], weights1)
        if first_digit != int(cnpj[12]):
            return False
        
        # Segundo dígito
        weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        second_digit = calculate_digit(cnpj[:13], weights2)
        if second_digit != int(cnpj[13]):
            return False
        
        return True
    
    def _validate_date(self, date_str: str) -> bool:
        """Validar data."""
        # Extrair componentes
        match = re.match(r'(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})', date_str)
        if not match:
            return False
        
        day, month, year = match.groups()
        day, month, year = int(day), int(month), int(year)
        
        # Ajustar ano se necessário
        if year < 100:
            year += 2000 if year < 50 else 1900
        
        # Validar ranges
        if month < 1 or month > 12:
            return False
        if day < 1 or day > 31:
            return False
        if year < 1900 or year > 2100:
            return False
        
        # Validar dias por mês
        days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        
        # Verificar ano bissexto
        if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
            days_in_month[1] = 29
        
        if day > days_in_month[month - 1]:
            return False
        
        return True
    
    def _validate_time(self, time_str: str) -> bool:
        """Validar horário."""
        match = re.match(r'(\d{1,2}):(\d{2})(:\d{2})?', time_str)
        if not match:
            return False
        
        hour, minute, second = match.groups()
        hour, minute = int(hour), int(minute)
        
        if hour < 0 or hour > 23:
            return False
        if minute < 0 or minute > 59:
            return False
        
        if second:
            second = int(second[1:])  # Remover ':'
            if second < 0 or second > 59:
                return False
        
        return True
    
    def _validate_email(self, email: str) -> bool:
        """Validar email."""
        # Validação básica
        if '@' not in email or '.' not in email:
            return False
        
        local, domain = email.rsplit('@', 1)
        
        # Verificar local
        if len(local) < 1 or len(local) > 64:
            return False
        
        # Verificar domínio
        if len(domain) < 1 or len(domain) > 255:
            return False
        
        if not re.match(r'^[a-zA-Z0-9.-]+$', domain):
            return False
        
        return True
    
    def _update_processing_stats(self, metrics: TextProcessingMetrics):
        """Atualizar estatísticas de processamento."""
        self.processing_stats['texts_processed'] += 1
        self.processing_stats['total_corrections'] += metrics.words_corrected
        self.processing_stats['total_patterns_found'] += metrics.patterns_detected
        
        # Atualizar médias
        total_texts = self.processing_stats['texts_processed']
        
        if total_texts == 1:
            self.processing_stats['avg_confidence_improvement'] = metrics.confidence_improvement
            self.processing_stats['avg_processing_time'] = metrics.processing_time
        else:
            # Média móvel
            current_conf = self.processing_stats['avg_confidence_improvement']
            new_conf = (current_conf * (total_texts - 1) + metrics.confidence_improvement) / total_texts
            self.processing_stats['avg_confidence_improvement'] = new_conf
            
            current_time = self.processing_stats['avg_processing_time']
            new_time = (current_time * (total_texts - 1) + metrics.processing_time) / total_texts
            self.processing_stats['avg_processing_time'] = new_time
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Obter estatísticas de processamento."""
        return {
            'texts_processed': self.processing_stats['texts_processed'],
            'total_corrections': self.processing_stats['total_corrections'],
            'total_patterns_found': self.processing_stats['total_patterns_found'],
            'avg_corrections_per_text': self.processing_stats['total_corrections'] / max(1, self.processing_stats['texts_processed']),
            'avg_patterns_per_text': self.processing_stats['total_patterns_found'] / max(1, self.processing_stats['texts_processed']),
            'avg_confidence_improvement': self.processing_stats['avg_confidence_improvement'],
            'avg_processing_time': self.processing_stats['avg_processing_time'],
            'language': self.language,
            'patterns_available': list(self.patterns.keys()),
            'corrections_available': len(self.ocr_corrections)
        }
    
    def generate_processing_report(self, metrics: TextProcessingMetrics) -> str:
        """Gerar relatório de processamento."""
        report = f"""
📝 RELATÓRIO DE PÓS-PROCESSAMENTO DE TEXTO

📊 Métricas Gerais:
   • Texto original: {metrics.original_length} caracteres
   • Texto processado: {metrics.processed_length} caracteres
   • Tempo de processamento: {metrics.processing_time:.3f}s

🔧 Correções Aplicadas:
   • Total de palavras corrigidas: {metrics.words_corrected}
   • Tipos de correção: {', '.join(metrics.corrections_applied)}

🎯 Padrões Detectados:
   • Total de padrões encontrados: {metrics.patterns_detected}
"""
        
        for pattern_type, patterns in metrics.patterns_found.items():
            if patterns:
                report += f"   • {pattern_type}: {len(patterns)} encontrados\n"
                for pattern in patterns[:3]:  # Mostrar até 3 exemplos
                    report += f"     - {pattern}\n"
                if len(patterns) > 3:
                    report += f"     ... e mais {len(patterns) - 3}\n"
        
        report += f"""
📈 Melhoria Estimada:
   • Aumento de confiança: +{metrics.confidence_improvement:.1%}
   • Qualidade do texto: {'Muito melhorada' if metrics.confidence_improvement > 0.2 else 'Melhorada' if metrics.confidence_improvement > 0.1 else 'Ligeiramente melhorada'}
"""
        
        return report


# Factory function
def create_text_processor(language: str = "pt-BR") -> TextProcessor:
    """Criar instância do processador de texto."""
    return TextProcessor(language)


# Example usage
if __name__ == "__main__":
    # Exemplo de uso
    processor = create_text_processor("pt-BR")
    
    # Texto de exemplo com problemas típicos de OCR
    sample_text = """
    DOCIJMENTO DE TESTE
    
    Este é um texto com erros tipicos de OCR.
    O nome do cliente é João da Silva, CPF: 123.456.789-01
    Telefone: (11) 99999-9999
    Email: joao@exemplo.com
    
    Data: 09/07/2025
    Valor: R$ 1.500,00
    
    Observacoes: nao houve problemas durante o processamento.
    """
    
    print("📝 Processador de Texto para OCR")
    print("=" * 40)
    
    # Processar texto
    processed_text, metrics = processor.process_text(sample_text)
    
    print("📊 Texto Original:")
    print(sample_text)
    print("\n📝 Texto Processado:")
    print(processed_text)
    
    # Mostrar relatório
    report = processor.generate_processing_report(metrics)
    print(report)
    
    # Estatísticas do processador
    stats = processor.get_processing_statistics()
    print(f"\n📊 Estatísticas Gerais:")
    print(f"  • Textos processados: {stats['texts_processed']}")
    print(f"  • Correções médias: {stats['avg_corrections_per_text']:.1f}")
    print(f"  • Padrões médios: {stats['avg_patterns_per_text']:.1f}")
    print(f"  • Melhoria média: {stats['avg_confidence_improvement']:.1%}")