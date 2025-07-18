"""
Sistema de busca semântica para documentos OCR
Utiliza embeddings vetoriais para busca por similaridade
"""

import sqlite3
import pickle
import hashlib
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
# Imports opcionais
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

@dataclass
class SemanticResult:
    """Resultado de busca semântica"""
    document_id: str
    chunk_id: int
    text_chunk: str
    similarity_score: float
    embedding_model: str
    created_at: datetime

class SemanticSearchEngine:
    """Motor de busca semântica para documentos OCR"""
    
    def __init__(self, db_path: str = None, model_name: str = None):
        self.db_path = db_path or Path.home() / ".claude" / "semantic_search.db"
        self.db_path.parent.mkdir(exist_ok=True)
        
        self.logger = logging.getLogger(__name__)
        
        # Configuração do modelo
        self.model_name = model_name or "sentence-transformers/all-MiniLM-L6-v2"
        self.embedding_model = None
        self.embedding_dim = 384  # Dimensão padrão do modelo MiniLM
        
        # Cache de embeddings
        self.embedding_cache = {}
        
        # Configurações
        self.chunk_size = 512
        self.chunk_overlap = 50
        self.similarity_threshold = 0.6
        
        self.init_database()
        self.load_model()
    
    def init_database(self):
        """Inicializa banco de dados para embeddings"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Tabela de embeddings
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS semantic_embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL,
                    chunk_id INTEGER NOT NULL,
                    text_chunk TEXT NOT NULL,
                    chunk_hash TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    embedding_model TEXT NOT NULL,
                    embedding_dim INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(document_id, chunk_id, chunk_hash)
                )
            """)
            
            # Tabela de configurações
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS semantic_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Índices para performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_document_id ON semantic_embeddings(document_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_model ON semantic_embeddings(embedding_model)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON semantic_embeddings(created_at)")
            
            conn.commit()
            conn.close()
            
            self.logger.info("Banco de dados semântico inicializado")
            
        except Exception as e:
            self.logger.error(f"Erro ao inicializar banco semântico: {e}")
    
    def load_model(self):
        """Carrega modelo de embedding"""
        try:
            if not SENTENCE_TRANSFORMERS_AVAILABLE:
                self.logger.warning("sentence-transformers não disponível")
                return
            
            self.logger.info(f"Carregando modelo: {self.model_name}")
            self.embedding_model = SentenceTransformer(self.model_name)
            
            # Determinar dimensão do embedding
            test_embedding = self.embedding_model.encode(["test"])
            self.embedding_dim = len(test_embedding[0])
            
            self.logger.info(f"Modelo carregado. Dimensão: {self.embedding_dim}")
            
        except Exception as e:
            self.logger.error(f"Erro ao carregar modelo de embedding: {e}")
            self.embedding_model = None
    
    def split_text_into_chunks(self, text: str) -> List[str]:
        """Divide texto em chunks para embedding"""
        if not text or len(text.strip()) < 10:
            return []
        
        words = text.split()
        chunks = []
        current_chunk = []
        current_length = 0
        
        for word in words:
            word_length = len(word)
            
            # Se adicionar esta palavra exceder o tamanho do chunk
            if current_length + word_length + 1 > self.chunk_size:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                    
                    # Manter overlap
                    overlap_words = current_chunk[-self.chunk_overlap:]
                    current_chunk = overlap_words + [word]
                    current_length = sum(len(w) for w in current_chunk) + len(current_chunk)
                else:
                    current_chunk = [word]
                    current_length = word_length
            else:
                current_chunk.append(word)
                current_length += word_length + 1
        
        # Adicionar último chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def calculate_text_hash(self, text: str) -> str:
        """Calcula hash do texto para cache"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    async def create_embeddings(self, document_id: str, text: str) -> bool:
        """Cria embeddings para um documento"""
        try:
            if not self.embedding_model:
                self.logger.warning("Modelo de embedding não disponível")
                return False
            
            # Dividir texto em chunks
            chunks = self.split_text_into_chunks(text)
            if not chunks:
                self.logger.warning(f"Nenhum chunk gerado para documento {document_id}")
                return False
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Remover embeddings antigos
            cursor.execute("DELETE FROM semantic_embeddings WHERE document_id = ?", (document_id,))
            
            embeddings_created = 0
            
            for chunk_id, chunk_text in enumerate(chunks):
                chunk_hash = self.calculate_text_hash(chunk_text)
                
                # Verificar se já existe embedding para este chunk
                cursor.execute("""
                    SELECT id FROM semantic_embeddings 
                    WHERE document_id = ? AND chunk_id = ? AND chunk_hash = ?
                """, (document_id, chunk_id, chunk_hash))
                
                if cursor.fetchone():
                    continue  # Já existe
                
                # Criar embedding
                embedding = self.embedding_model.encode([chunk_text])[0]
                embedding_blob = pickle.dumps(embedding)
                
                # Salvar no banco
                cursor.execute("""
                    INSERT INTO semantic_embeddings 
                    (document_id, chunk_id, text_chunk, chunk_hash, embedding, 
                     embedding_model, embedding_dim, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    document_id, chunk_id, chunk_text, chunk_hash, embedding_blob,
                    self.model_name, self.embedding_dim, datetime.now().isoformat()
                ))
                
                embeddings_created += 1
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Embeddings criados para documento {document_id}: {embeddings_created} chunks")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao criar embeddings: {e}")
            return False
    
    async def search_similar(self, query: str, max_results: int = 10, 
                           min_similarity: float = None) -> List[SemanticResult]:
        """Busca documentos similares usando embeddings"""
        try:
            if not self.embedding_model:
                self.logger.warning("Modelo de embedding não disponível")
                return []
            
            # Criar embedding da query
            query_embedding = self.embedding_model.encode([query])[0]
            
            # Buscar embeddings no banco
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT document_id, chunk_id, text_chunk, embedding, 
                       embedding_model, created_at
                FROM semantic_embeddings
                WHERE embedding_model = ?
                ORDER BY created_at DESC
            """, (self.model_name,))
            
            results = []
            min_sim = min_similarity or self.similarity_threshold
            
            for row in cursor.fetchall():
                doc_id, chunk_id, text_chunk, embedding_blob, model, created_at = row
                
                # Deserializar embedding
                try:
                    embedding = pickle.loads(embedding_blob)
                except Exception as e:
                    self.logger.warning(f"Erro ao deserializar embedding: {e}")
                    continue
                
                # Calcular similaridade
                if SKLEARN_AVAILABLE:
                    similarity = cosine_similarity(
                        [query_embedding], [embedding]
                    )[0][0]
                else:
                    # Fallback para cálculo manual
                    similarity = self.calculate_cosine_similarity(query_embedding, embedding)
                
                # Filtrar por similaridade mínima
                if similarity >= min_sim:
                    result = SemanticResult(
                        document_id=doc_id,
                        chunk_id=chunk_id,
                        text_chunk=text_chunk,
                        similarity_score=similarity,
                        embedding_model=model,
                        created_at=datetime.fromisoformat(created_at)
                    )
                    results.append(result)
            
            conn.close()
            
            # Ordenar por similaridade decrescente
            results.sort(key=lambda x: x.similarity_score, reverse=True)
            
            return results[:max_results]
            
        except Exception as e:
            self.logger.error(f"Erro na busca semântica: {e}")
            return []
    
    def calculate_cosine_similarity(self, vec1, vec2) -> float:
        """Calcula similaridade coseno manualmente"""
        try:
            if not NUMPY_AVAILABLE:
                # Fallback simples sem numpy
                dot_product = sum(a * b for a, b in zip(vec1, vec2))
                norm1 = sum(a * a for a in vec1) ** 0.5
                norm2 = sum(b * b for b in vec2) ** 0.5
            else:
                dot_product = np.dot(vec1, vec2)
                norm1 = np.linalg.norm(vec1)
                norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return dot_product / (norm1 * norm2)
            
        except Exception as e:
            self.logger.error(f"Erro ao calcular similaridade: {e}")
            return 0.0
    
    async def get_document_embeddings_count(self, document_id: str) -> int:
        """Retorna número de embeddings para um documento"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT COUNT(*) FROM semantic_embeddings WHERE document_id = ?",
                (document_id,)
            )
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count
            
        except Exception as e:
            self.logger.error(f"Erro ao contar embeddings: {e}")
            return 0
    
    async def delete_document_embeddings(self, document_id: str) -> bool:
        """Remove embeddings de um documento"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "DELETE FROM semantic_embeddings WHERE document_id = ?",
                (document_id,)
            )
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            self.logger.info(f"Embeddings removidos para documento {document_id}: {deleted_count}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao remover embeddings: {e}")
            return False
    
    async def clear_all_embeddings(self) -> bool:
        """Remove todos os embeddings"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM semantic_embeddings")
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            self.logger.info(f"Todos os embeddings removidos: {deleted_count}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao limpar embeddings: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estatísticas dos embeddings"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Estatísticas gerais
            cursor.execute("SELECT COUNT(*) FROM semantic_embeddings")
            total_embeddings = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT document_id) FROM semantic_embeddings")
            total_documents = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT embedding_model) FROM semantic_embeddings")
            total_models = cursor.fetchone()[0]
            
            # Estatísticas por modelo
            cursor.execute("""
                SELECT embedding_model, COUNT(*) as count, AVG(embedding_dim) as avg_dim
                FROM semantic_embeddings
                GROUP BY embedding_model
            """)
            
            models_stats = {}
            for row in cursor.fetchall():
                model, count, avg_dim = row
                models_stats[model] = {
                    'count': count,
                    'avg_dimension': int(avg_dim) if avg_dim else 0
                }
            
            # Documentos mais recentes
            cursor.execute("""
                SELECT document_id, MAX(created_at) as last_updated
                FROM semantic_embeddings
                GROUP BY document_id
                ORDER BY last_updated DESC
                LIMIT 5
            """)
            
            recent_documents = []
            for row in cursor.fetchall():
                doc_id, last_updated = row
                recent_documents.append({
                    'document_id': doc_id,
                    'last_updated': last_updated
                })
            
            conn.close()
            
            return {
                'total_embeddings': total_embeddings,
                'total_documents': total_documents,
                'total_models': total_models,
                'current_model': self.model_name,
                'embedding_dimension': self.embedding_dim,
                'model_available': self.embedding_model is not None,
                'models_stats': models_stats,
                'recent_documents': recent_documents,
                'chunk_size': self.chunk_size,
                'similarity_threshold': self.similarity_threshold
            }
            
        except Exception as e:
            self.logger.error(f"Erro ao obter estatísticas: {e}")
            return {}
    
    def set_similarity_threshold(self, threshold: float):
        """Define threshold de similaridade"""
        if 0.0 <= threshold <= 1.0:
            self.similarity_threshold = threshold
            self.logger.info(f"Threshold de similaridade definido para: {threshold}")
        else:
            self.logger.warning(f"Threshold inválido: {threshold}. Deve estar entre 0.0 e 1.0")
    
    def set_chunk_size(self, size: int):
        """Define tamanho dos chunks"""
        if size > 0:
            self.chunk_size = size
            self.logger.info(f"Tamanho do chunk definido para: {size}")
        else:
            self.logger.warning(f"Tamanho de chunk inválido: {size}")
    
    def is_available(self) -> bool:
        """Verifica se busca semântica está disponível"""
        return (SENTENCE_TRANSFORMERS_AVAILABLE and 
                self.embedding_model is not None)
    
    def get_requirements(self) -> List[str]:
        """Retorna lista de dependências necessárias"""
        requirements = []
        
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            requirements.append("sentence-transformers")
        
        if not SKLEARN_AVAILABLE:
            requirements.append("scikit-learn")
        
        if not OPENAI_AVAILABLE:
            requirements.append("openai")
        
        return requirements

# Função de conveniência para criar instância
def create_semantic_search_engine(model_name: str = None) -> SemanticSearchEngine:
    """Cria instância do motor de busca semântica"""
    return SemanticSearchEngine(model_name=model_name)