"""
Sistema de Cache Inteligente para OCR Enhanced.

Este módulo implementa um sistema de cache robusto que evita reprocessamento
desnecessário de arquivos, economizando tempo e recursos.
"""

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import os
import shutil

from .logger import get_logger


class OCRCacheManager:
    """
    Gerenciador de cache inteligente para resultados de OCR.
    
    Funcionalidades:
    - Hash único por arquivo baseado em conteúdo
    - Armazenamento em SQLite + JSON
    - Validação de integridade automática
    - Limpeza automática de cache antigo
    - Estatísticas de uso do cache
    """
    
    def __init__(self, cache_dir: Optional[str] = None, max_age_days: int = 30):
        """
        Inicializar gerenciador de cache.
        
        Args:
            cache_dir: Diretório para armazenar cache (padrão: ~/.ocr_cache)
            max_age_days: Idade máxima dos itens em cache (padrão: 30 dias)
        """
        self.logger = get_logger("cache_manager")
        
        # Configuração do diretório de cache
        if cache_dir is None:
            cache_dir = Path.home() / ".ocr_cache"
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Subdirectórios
        self.results_dir = self.cache_dir / "results"
        self.results_dir.mkdir(exist_ok=True)
        
        self.thumbnails_dir = self.cache_dir / "thumbnails"
        self.thumbnails_dir.mkdir(exist_ok=True)
        
        # Configurações
        self.max_age_days = max_age_days
        self.db_path = self.cache_dir / "cache.db"
        
        # Estatísticas
        self.stats = {
            'hits': 0,
            'misses': 0,
            'saves': 0,
            'errors': 0,
            'bytes_saved': 0
        }
        
        # Inicializar banco de dados
        self._init_database()
        
        self.logger.info(f"Cache inicializado em: {self.cache_dir}")
    
    def _init_database(self):
        """Inicializar banco de dados SQLite."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cache_entries (
                        file_hash TEXT PRIMARY KEY,
                        original_filename TEXT NOT NULL,
                        file_size INTEGER NOT NULL,
                        file_mtime REAL NOT NULL,
                        processing_engine TEXT NOT NULL,
                        processing_options TEXT NOT NULL,
                        result_path TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        accessed_at REAL NOT NULL,
                        access_count INTEGER DEFAULT 1,
                        confidence REAL,
                        processing_time REAL,
                        word_count INTEGER,
                        character_count INTEGER,
                        success BOOLEAN NOT NULL
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_file_hash ON cache_entries(file_hash)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_created_at ON cache_entries(created_at)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_accessed_at ON cache_entries(accessed_at)
                """)
                
                conn.commit()
                
            self.logger.info("Banco de dados de cache inicializado")
            
        except Exception as e:
            self.logger.error(f"Erro ao inicializar banco de dados: {e}")
            raise
    
    def _calculate_file_hash(self, file_path: Path, 
                           processing_options: Dict[str, Any] = None) -> str:
        """
        Calcular hash único para um arquivo.
        
        O hash inclui:
        - Conteúdo do arquivo (SHA-256)
        - Opções de processamento
        - Tamanho do arquivo
        - Data de modificação
        
        Args:
            file_path: Caminho para o arquivo
            processing_options: Opções de processamento OCR
            
        Returns:
            String hash única
        """
        try:
            # Hash do conteúdo do arquivo
            file_hasher = hashlib.sha256()
            
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    file_hasher.update(chunk)
            
            content_hash = file_hasher.hexdigest()
            
            # Informações do arquivo
            stat = file_path.stat()
            file_info = {
                'content_hash': content_hash,
                'size': stat.st_size,
                'mtime': stat.st_mtime,
                'filename': file_path.name
            }
            
            # Adicionar opções de processamento
            if processing_options:
                # Normalizar opções para hash consistente
                normalized_options = self._normalize_options(processing_options)
                file_info['options'] = normalized_options
            
            # Hash final
            combined_data = json.dumps(file_info, sort_keys=True).encode('utf-8')
            final_hash = hashlib.sha256(combined_data).hexdigest()
            
            return final_hash
            
        except Exception as e:
            self.logger.error(f"Erro ao calcular hash do arquivo {file_path}: {e}")
            raise
    
    def _normalize_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizar opções de processamento para hash consistente."""
        normalized = {}
        
        # Chaves importantes para o cache
        important_keys = [
            'language', 'confidence_threshold', 'engine', 
            'preprocessing', 'dpi', 'quality_threshold'
        ]
        
        for key in important_keys:
            if key in options:
                value = options[key]
                # Converter para string para serialização consistente
                if isinstance(value, (list, tuple)):
                    value = sorted(str(v) for v in value)
                normalized[key] = str(value)
        
        return normalized
    
    def get_cached_result(self, file_path: Path, 
                         processing_options: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Buscar resultado em cache para um arquivo.
        
        Args:
            file_path: Caminho para o arquivo
            processing_options: Opções de processamento OCR
            
        Returns:
            Resultado do OCR em cache ou None se não encontrado
        """
        try:
            # Verificar se arquivo existe
            if not file_path.exists():
                return None
            
            # Calcular hash
            file_hash = self._calculate_file_hash(file_path, processing_options)
            
            # Buscar no banco de dados
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM cache_entries WHERE file_hash = ?
                """, (file_hash,))
                
                row = cursor.fetchone()
                
                if not row:
                    self.stats['misses'] += 1
                    self.logger.debug(f"Cache miss para: {file_path.name}")
                    return None
                
                # Verificar se arquivo de resultado existe
                result_path = Path(row['result_path'])
                if not result_path.exists():
                    self.logger.warning(f"Arquivo de resultado não encontrado: {result_path}")
                    # Remover entrada inválida
                    conn.execute("DELETE FROM cache_entries WHERE file_hash = ?", (file_hash,))
                    conn.commit()
                    self.stats['misses'] += 1
                    return None
                
                # Verificar idade do cache
                created_at = datetime.fromtimestamp(row['created_at'])
                age = datetime.now() - created_at
                
                if age.days > self.max_age_days:
                    self.logger.info(f"Cache expirado para: {file_path.name} (idade: {age.days} dias)")
                    self._remove_cache_entry(file_hash)
                    self.stats['misses'] += 1
                    return None
                
                # Carregar resultado
                try:
                    with open(result_path, 'r', encoding='utf-8') as f:
                        result = json.load(f)
                    
                    # Atualizar estatísticas de acesso
                    conn.execute("""
                        UPDATE cache_entries 
                        SET accessed_at = ?, access_count = access_count + 1
                        WHERE file_hash = ?
                    """, (time.time(), file_hash))
                    conn.commit()
                    
                    self.stats['hits'] += 1
                    self.stats['bytes_saved'] += result_path.stat().st_size
                    
                    self.logger.info(f"Cache hit para: {file_path.name} "
                                   f"(engine: {row['processing_engine']}, "
                                   f"confidence: {row['confidence']:.2f})")
                    
                    return result
                    
                except Exception as e:
                    self.logger.error(f"Erro ao carregar resultado do cache: {e}")
                    self._remove_cache_entry(file_hash)
                    self.stats['errors'] += 1
                    return None
                
        except Exception as e:
            self.logger.error(f"Erro ao buscar cache para {file_path}: {e}")
            self.stats['errors'] += 1
            return None
    
    def save_result(self, file_path: Path, result: Dict[str, Any], 
                   processing_options: Dict[str, Any] = None,
                   engine_used: str = "unknown") -> bool:
        """
        Salvar resultado de OCR no cache.
        
        Args:
            file_path: Caminho para o arquivo original
            result: Resultado do OCR
            processing_options: Opções de processamento utilizadas
            engine_used: Engine OCR utilizado
            
        Returns:
            True se salvou com sucesso, False caso contrário
        """
        try:
            if not file_path.exists():
                self.logger.warning(f"Arquivo não existe para cache: {file_path}")
                return False
            
            # Calcular hash
            file_hash = self._calculate_file_hash(file_path, processing_options)
            
            # Preparar caminho do resultado
            result_filename = f"{file_hash}.json"
            result_path = self.results_dir / result_filename
            
            # Salvar resultado em JSON
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            # Extrair metadados do resultado
            metadata = result.get('metadata', {})
            confidence = metadata.get('average_confidence', 0.0)
            processing_time = metadata.get('processing_time', 0.0)
            
            # Contar palavras e caracteres
            word_count = 0
            character_count = 0
            pages = result.get('pages', [])
            
            for page in pages:
                text = page.get('text', '')
                word_count += len(text.split())
                character_count += len(text)
            
            # Salvar no banco de dados
            stat = file_path.stat()
            current_time = time.time()
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO cache_entries (
                        file_hash, original_filename, file_size, file_mtime,
                        processing_engine, processing_options, result_path,
                        created_at, accessed_at, access_count,
                        confidence, processing_time, word_count, character_count, success
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    file_hash, file_path.name, stat.st_size, stat.st_mtime,
                    engine_used, json.dumps(processing_options or {}), str(result_path),
                    current_time, current_time, 1,
                    confidence, processing_time, word_count, character_count,
                    result.get('success', True)
                ))
                conn.commit()
            
            self.stats['saves'] += 1
            
            self.logger.info(f"Resultado salvo no cache: {file_path.name} "
                           f"(engine: {engine_used}, confidence: {confidence:.2f})")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao salvar no cache: {e}")
            self.stats['errors'] += 1
            return False
    
    def _remove_cache_entry(self, file_hash: str):
        """Remover entrada do cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Buscar caminho do arquivo
                cursor = conn.execute("SELECT result_path FROM cache_entries WHERE file_hash = ?", 
                                    (file_hash,))
                row = cursor.fetchone()
                
                if row:
                    result_path = Path(row[0])
                    if result_path.exists():
                        result_path.unlink()
                
                # Remover do banco
                conn.execute("DELETE FROM cache_entries WHERE file_hash = ?", (file_hash,))
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Erro ao remover entrada do cache: {e}")
    
    def cleanup_old_entries(self) -> int:
        """
        Limpar entradas antigas do cache.
        
        Returns:
            Número de entradas removidas
        """
        try:
            cutoff_time = time.time() - (self.max_age_days * 24 * 3600)
            removed_count = 0
            
            with sqlite3.connect(self.db_path) as conn:
                # Buscar entradas antigas
                cursor = conn.execute("""
                    SELECT file_hash, result_path FROM cache_entries 
                    WHERE created_at < ?
                """, (cutoff_time,))
                
                old_entries = cursor.fetchall()
                
                for file_hash, result_path in old_entries:
                    # Remover arquivo de resultado
                    try:
                        Path(result_path).unlink(missing_ok=True)
                    except Exception as e:
                        self.logger.warning(f"Erro ao remover arquivo: {e}")
                    
                    removed_count += 1
                
                # Remover do banco
                conn.execute("DELETE FROM cache_entries WHERE created_at < ?", (cutoff_time,))
                conn.commit()
            
            if removed_count > 0:
                self.logger.info(f"Limpeza do cache: {removed_count} entradas antigas removidas")
            
            return removed_count
            
        except Exception as e:
            self.logger.error(f"Erro na limpeza do cache: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obter estatísticas do cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_entries,
                        SUM(file_size) as total_file_size,
                        SUM(access_count) as total_accesses,
                        AVG(confidence) as avg_confidence,
                        AVG(processing_time) as avg_processing_time,
                        COUNT(CASE WHEN success = 1 THEN 1 END) as successful_entries
                    FROM cache_entries
                """)
                
                row = cursor.fetchone()
                
                # Calcular tamanho do cache em disco
                cache_size = sum(
                    f.stat().st_size 
                    for f in self.results_dir.glob("*.json")
                    if f.is_file()
                )
                
                stats = {
                    'total_entries': row[0] or 0,
                    'total_file_size_mb': (row[1] or 0) / (1024 * 1024),
                    'cache_size_mb': cache_size / (1024 * 1024),
                    'total_accesses': row[2] or 0,
                    'avg_confidence': row[3] or 0.0,
                    'avg_processing_time': row[4] or 0.0,
                    'success_rate': (row[5] or 0) / max(row[0] or 1, 1),
                    'hit_rate': self.stats['hits'] / max(self.stats['hits'] + self.stats['misses'], 1),
                    'runtime_stats': self.stats.copy()
                }
                
                return stats
                
        except Exception as e:
            self.logger.error(f"Erro ao obter estatísticas: {e}")
            return {'error': str(e)}
    
    def clear_cache(self) -> bool:
        """Limpar todo o cache."""
        try:
            # Remover arquivos de resultado
            for file_path in self.results_dir.glob("*.json"):
                file_path.unlink()
            
            # Limpar banco de dados
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM cache_entries")
                conn.commit()
            
            # Resetar estatísticas
            self.stats = {
                'hits': 0,
                'misses': 0,
                'saves': 0,
                'errors': 0,
                'bytes_saved': 0
            }
            
            self.logger.info("Cache completamente limpo")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao limpar cache: {e}")
            return False
    
    def get_cached_files_list(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Obter lista de arquivos em cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT 
                        original_filename, processing_engine, confidence,
                        processing_time, created_at, accessed_at, access_count,
                        word_count, character_count, success
                    FROM cache_entries 
                    ORDER BY accessed_at DESC 
                    LIMIT ?
                """, (limit,))
                
                files = []
                for row in cursor:
                    files.append({
                        'filename': row['original_filename'],
                        'engine': row['processing_engine'],
                        'confidence': row['confidence'],
                        'processing_time': row['processing_time'],
                        'created_at': datetime.fromtimestamp(row['created_at']).isoformat(),
                        'accessed_at': datetime.fromtimestamp(row['accessed_at']).isoformat(),
                        'access_count': row['access_count'],
                        'word_count': row['word_count'],
                        'character_count': row['character_count'],
                        'success': bool(row['success'])
                    })
                
                return files
                
        except Exception as e:
            self.logger.error(f"Erro ao obter lista de arquivos: {e}")
            return []


# Factory function
def create_cache_manager(cache_dir: Optional[str] = None, 
                        max_age_days: int = 30) -> OCRCacheManager:
    """Criar instância do gerenciador de cache."""
    return OCRCacheManager(cache_dir, max_age_days)


# Example usage
if __name__ == "__main__":
    # Exemplo de uso
    cache = create_cache_manager()
    
    print("Sistema de Cache OCR Enhanced")
    print("=" * 40)
    
    stats = cache.get_cache_stats()
    print(f"Entradas em cache: {stats['total_entries']}")
    print(f"Tamanho do cache: {stats['cache_size_mb']:.2f} MB")
    print(f"Taxa de acerto: {stats['hit_rate']:.2%}")
    
    # Limpeza automática
    removed = cache.cleanup_old_entries()
    if removed > 0:
        print(f"Limpeza: {removed} entradas antigas removidas")