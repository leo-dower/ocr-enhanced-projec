"""
Sistema de busca inteligente com Elasticsearch para documentos OCR
Integra com MCP para indexação e busca semântica avançada
"""

import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import hashlib
import sqlite3
from pathlib import Path

@dataclass
class SearchResult:
    """Resultado de busca em documento"""
    document_id: str
    file_path: str
    title: str
    content_excerpt: str
    confidence: float
    page_number: int
    match_type: str  # 'exact', 'fuzzy', 'semantic'
    score: float
    metadata: Dict[str, Any]

@dataclass
class DocumentIndex:
    """Índice de documento para busca"""
    id: str
    file_path: str
    title: str
    content: str
    pages: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    indexed_at: datetime
    content_hash: str

class SearchManager:
    """Gerenciador de busca inteligente para documentos OCR"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.expanduser("~/.claude/search_config.json")
        self.logger = logging.getLogger(__name__)
        
        # Configuração do índice local (SQLite para demonstração)
        self.db_path = Path.home() / ".claude" / "search_index.db"
        self.db_path.parent.mkdir(exist_ok=True)
        
        # Configurações
        self.elasticsearch_enabled = False
        self.semantic_search_enabled = False
        self.embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
        
        self.load_config()
        self.init_local_index()
    
    def load_config(self):
        """Carrega configuração do sistema de busca"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    self.elasticsearch_enabled = config.get('elasticsearch_enabled', False)
                    self.semantic_search_enabled = config.get('semantic_search_enabled', False)
                    self.embedding_model = config.get('embedding_model', self.embedding_model)
                    self.logger.info("Configuração de busca carregada")
        except Exception as e:
            self.logger.error(f"Erro ao carregar configuração de busca: {e}")
    
    def save_config(self):
        """Salva configuração do sistema de busca"""
        try:
            config = {
                'elasticsearch_enabled': self.elasticsearch_enabled,
                'semantic_search_enabled': self.semantic_search_enabled,
                'embedding_model': self.embedding_model,
                'last_updated': datetime.now().isoformat()
            }
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            self.logger.error(f"Erro ao salvar configuração de busca: {e}")
    
    def init_local_index(self):
        """Inicializa índice local SQLite"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Tabela de documentos indexados
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS indexed_documents (
                    id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    indexed_at TEXT NOT NULL,
                    page_count INTEGER DEFAULT 0
                )
            """)
            
            # Tabela de páginas (para busca por página)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document_pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    confidence REAL DEFAULT 0.0,
                    FOREIGN KEY (document_id) REFERENCES indexed_documents (id)
                )
            """)
            
            # Tabela de embeddings (para busca semântica)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL,
                    page_number INTEGER,
                    text_chunk TEXT NOT NULL,
                    embedding BLOB,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES indexed_documents (id)
                )
            """)
            
            # Índices para performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_content_fts ON indexed_documents(content)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pages_content ON document_pages(content)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_path ON indexed_documents(file_path)")
            
            conn.commit()
            conn.close()
            
            self.logger.info("Índice local inicializado com sucesso")
            
        except Exception as e:
            self.logger.error(f"Erro ao inicializar índice local: {e}")
    
    def calculate_content_hash(self, content: str) -> str:
        """Calcula hash do conteúdo para detectar mudanças"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    async def index_document(self, ocr_result: Dict[str, Any], file_path: str) -> bool:
        """Indexa documento OCR para busca"""
        try:
            # Extrair informações do resultado OCR
            pages = ocr_result.get('pages', [])
            metadata = ocr_result.get('metadata', {})
            
            # Combinar texto de todas as páginas
            full_content = []
            for page in pages:
                content = page.get('content', '')
                if content:
                    full_content.append(content)
            
            content_text = '\n\n'.join(full_content)
            content_hash = self.calculate_content_hash(content_text)
            
            # Criar ID único para o documento
            doc_id = hashlib.md5(file_path.encode('utf-8')).hexdigest()
            
            # Verificar se documento já foi indexado
            if await self.is_document_indexed(doc_id, content_hash):
                self.logger.info(f"Documento já indexado: {os.path.basename(file_path)}")
                return True
            
            # Indexar no SQLite local
            await self.index_to_local_db(doc_id, file_path, content_text, pages, metadata, content_hash)
            
            # Indexar no Elasticsearch se disponível
            if self.elasticsearch_enabled:
                await self.index_to_elasticsearch(doc_id, file_path, content_text, pages, metadata)
            
            # Criar embeddings se busca semântica estiver ativa
            if self.semantic_search_enabled:
                await self.create_embeddings(doc_id, content_text, pages)
                
                # Também criar embeddings com motor semântico
                try:
                    from .semantic_search import SemanticSearchEngine
                    semantic_engine = SemanticSearchEngine()
                    if semantic_engine.is_available():
                        await semantic_engine.create_embeddings(doc_id, content_text)
                except Exception as e:
                    self.logger.error(f"Erro ao criar embeddings semânticos: {e}")
            
            self.logger.info(f"Documento indexado com sucesso: {os.path.basename(file_path)}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao indexar documento: {e}")
            return False
    
    async def is_document_indexed(self, doc_id: str, content_hash: str) -> bool:
        """Verifica se documento já foi indexado"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT content_hash FROM indexed_documents 
                WHERE id = ?
            """, (doc_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return result[0] == content_hash
            
            return False
            
        except Exception as e:
            self.logger.error(f"Erro ao verificar indexação: {e}")
            return False
    
    async def index_to_local_db(self, doc_id: str, file_path: str, content: str, 
                               pages: List[Dict], metadata: Dict, content_hash: str):
        """Indexa documento no banco local SQLite"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Inserir/atualizar documento
            cursor.execute("""
                INSERT OR REPLACE INTO indexed_documents 
                (id, file_path, title, content, content_hash, metadata, indexed_at, page_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                doc_id,
                file_path,
                os.path.basename(file_path),
                content,
                content_hash,
                json.dumps(metadata),
                datetime.now().isoformat(),
                len(pages)
            ))
            
            # Remover páginas antigas
            cursor.execute("DELETE FROM document_pages WHERE document_id = ?", (doc_id,))
            
            # Inserir páginas
            for i, page in enumerate(pages):
                page_content = page.get('content', '')
                confidence = page.get('confidence', 0.0)
                
                cursor.execute("""
                    INSERT INTO document_pages 
                    (document_id, page_number, content, confidence)
                    VALUES (?, ?, ?, ?)
                """, (doc_id, i + 1, page_content, confidence))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Erro ao indexar no banco local: {e}")
            raise
    
    async def index_to_elasticsearch(self, doc_id: str, file_path: str, content: str, 
                                   pages: List[Dict], metadata: Dict):
        """Indexa documento no Elasticsearch via MCP"""
        try:
            # Preparar documento para Elasticsearch
            es_doc = {
                'id': doc_id,
                'file_path': file_path,
                'title': os.path.basename(file_path),
                'content': content,
                'pages': pages,
                'metadata': metadata,
                'indexed_at': datetime.now().isoformat(),
                'page_count': len(pages)
            }
            
            # Aqui seria a chamada MCP para Elasticsearch
            # Por enquanto, apenas log
            self.logger.info(f"Documento preparado para Elasticsearch: {doc_id}")
            
        except Exception as e:
            self.logger.error(f"Erro ao indexar no Elasticsearch: {e}")
            raise
    
    async def create_embeddings(self, doc_id: str, content: str, pages: List[Dict]):
        """Cria embeddings para busca semântica"""
        try:
            # Dividir conteúdo em chunks para embeddings
            chunks = self.split_content_into_chunks(content, max_length=500)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Remover embeddings antigos
            cursor.execute("DELETE FROM embeddings WHERE document_id = ?", (doc_id,))
            
            # Criar embeddings para cada chunk
            for i, chunk in enumerate(chunks):
                if len(chunk.strip()) > 10:  # Apenas chunks com conteúdo relevante
                    # Aqui seria a chamada para criar embedding real
                    # Por enquanto, salvar sem embedding
                    cursor.execute("""
                        INSERT INTO embeddings 
                        (document_id, page_number, text_chunk, embedding, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (doc_id, None, chunk, None, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Embeddings criados para documento: {doc_id}")
            
        except Exception as e:
            self.logger.error(f"Erro ao criar embeddings: {e}")
            raise
    
    def split_content_into_chunks(self, content: str, max_length: int = 500) -> List[str]:
        """Divide conteúdo em chunks para embeddings"""
        words = content.split()
        chunks = []
        current_chunk = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + 1 <= max_length:
                current_chunk.append(word)
                current_length += len(word) + 1
            else:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_length = len(word)
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    async def search_documents(self, query: str, max_results: int = 10, 
                             search_type: str = 'mixed') -> List[SearchResult]:
        """Busca documentos usando diferentes estratégias"""
        try:
            results = []
            
            # Busca exata/fuzzy no conteúdo
            if search_type in ['exact', 'fuzzy', 'mixed']:
                exact_results = await self.search_exact(query, max_results)
                results.extend(exact_results)
            
            # Busca semântica se disponível
            if search_type in ['semantic', 'mixed'] and self.semantic_search_enabled:
                semantic_results = await self.search_semantic(query, max_results)
                results.extend(semantic_results)
            
            # Remover duplicatas e ordenar por score
            unique_results = {}
            for result in results:
                key = f"{result.document_id}_{result.page_number}"
                if key not in unique_results or result.score > unique_results[key].score:
                    unique_results[key] = result
            
            # Ordenar por score decrescente
            sorted_results = sorted(unique_results.values(), key=lambda x: x.score, reverse=True)
            
            return sorted_results[:max_results]
            
        except Exception as e:
            self.logger.error(f"Erro na busca: {e}")
            return []
    
    async def search_exact(self, query: str, max_results: int) -> List[SearchResult]:
        """Busca exata no conteúdo dos documentos"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Buscar em páginas individuais
            cursor.execute("""
                SELECT 
                    d.id, d.file_path, d.title, p.content, p.confidence, p.page_number,
                    d.metadata
                FROM indexed_documents d
                JOIN document_pages p ON d.id = p.document_id
                WHERE p.content LIKE ?
                ORDER BY p.confidence DESC
                LIMIT ?
            """, (f"%{query}%", max_results))
            
            results = []
            for row in cursor.fetchall():
                doc_id, file_path, title, content, confidence, page_num, metadata_json = row
                
                # Extrair excerto com contexto
                excerpt = self.extract_excerpt(content, query)
                
                result = SearchResult(
                    document_id=doc_id,
                    file_path=file_path,
                    title=title,
                    content_excerpt=excerpt,
                    confidence=confidence,
                    page_number=page_num,
                    match_type='exact',
                    score=confidence * 0.9,  # Score baseado na confiança OCR
                    metadata=json.loads(metadata_json)
                )
                results.append(result)
            
            conn.close()
            return results
            
        except Exception as e:
            self.logger.error(f"Erro na busca exata: {e}")
            return []
    
    async def search_semantic(self, query: str, max_results: int) -> List[SearchResult]:
        """Busca semântica usando embeddings"""
        try:
            # Importar motor de busca semântica
            from .semantic_search import SemanticSearchEngine
            
            # Criar instância do motor semântico
            semantic_engine = SemanticSearchEngine()
            
            if not semantic_engine.is_available():
                self.logger.warning("Motor de busca semântica não disponível")
                return []
            
            # Executar busca semântica
            semantic_results = await semantic_engine.search_similar(query, max_results)
            
            # Converter para SearchResult
            results = []
            for sem_result in semantic_results:
                # Buscar informações do documento
                doc_info = await self.get_document_info(sem_result.document_id)
                if doc_info:
                    result = SearchResult(
                        document_id=sem_result.document_id,
                        file_path=doc_info.get('file_path', ''),
                        title=doc_info.get('title', ''),
                        content_excerpt=sem_result.text_chunk,
                        confidence=0.8,  # Confiança padrão para busca semântica
                        page_number=0,  # Chunk não tem página específica
                        match_type='semantic',
                        score=sem_result.similarity_score,
                        metadata=doc_info.get('metadata', {})
                    )
                    results.append(result)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Erro na busca semântica: {e}")
            return []
    
    def extract_excerpt(self, content: str, query: str, context_length: int = 100) -> str:
        """Extrai excerto do conteúdo com contexto ao redor da query"""
        try:
            query_lower = query.lower()
            content_lower = content.lower()
            
            # Encontrar posição da query
            pos = content_lower.find(query_lower)
            if pos == -1:
                return content[:context_length] + "..."
            
            # Calcular início e fim do excerto
            start = max(0, pos - context_length // 2)
            end = min(len(content), pos + len(query) + context_length // 2)
            
            excerpt = content[start:end]
            
            # Adicionar "..." se necessário
            if start > 0:
                excerpt = "..." + excerpt
            if end < len(content):
                excerpt = excerpt + "..."
            
            return excerpt
            
        except Exception as e:
            self.logger.error(f"Erro ao extrair excerto: {e}")
            return content[:context_length] + "..."
    
    async def get_document_statistics(self) -> Dict[str, Any]:
        """Retorna estatísticas do índice de busca"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Estatísticas básicas
            cursor.execute("SELECT COUNT(*) FROM indexed_documents")
            total_docs = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(page_count) FROM indexed_documents")
            total_pages = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT COUNT(*) FROM embeddings")
            total_embeddings = cursor.fetchone()[0]
            
            # Documentos mais recentes
            cursor.execute("""
                SELECT title, indexed_at FROM indexed_documents 
                ORDER BY indexed_at DESC LIMIT 5
            """)
            recent_docs = cursor.fetchall()
            
            conn.close()
            
            return {
                'total_documents': total_docs,
                'total_pages': total_pages,
                'total_embeddings': total_embeddings,
                'elasticsearch_enabled': self.elasticsearch_enabled,
                'semantic_search_enabled': self.semantic_search_enabled,
                'recent_documents': [{'title': doc[0], 'indexed_at': doc[1]} for doc in recent_docs]
            }
            
        except Exception as e:
            self.logger.error(f"Erro ao obter estatísticas: {e}")
            return {}
    
    async def clear_index(self) -> bool:
        """Limpa todo o índice de busca"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM embeddings")
            cursor.execute("DELETE FROM document_pages")
            cursor.execute("DELETE FROM indexed_documents")
            
            conn.commit()
            conn.close()
            
            self.logger.info("Índice de busca limpo com sucesso")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao limpar índice: {e}")
            return False
    
    def enable_elasticsearch(self, enabled: bool = True):
        """Ativa/desativa integração com Elasticsearch"""
        self.elasticsearch_enabled = enabled
        self.save_config()
        self.logger.info(f"Elasticsearch {'ativado' if enabled else 'desativado'}")
    
    def enable_semantic_search(self, enabled: bool = True):
        """Ativa/desativa busca semântica"""
        self.semantic_search_enabled = enabled
        self.save_config()
        self.logger.info(f"Busca semântica {'ativada' if enabled else 'desativada'}")
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status do sistema de busca"""
        return {
            'elasticsearch_enabled': self.elasticsearch_enabled,
            'semantic_search_enabled': self.semantic_search_enabled,
            'embedding_model': self.embedding_model,
            'db_path': str(self.db_path),
            'config_path': self.config_path
        }
    
    async def get_document_info(self, document_id: str) -> Dict[str, Any]:
        """Busca informações de um documento pelo ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT file_path, title, metadata
                FROM indexed_documents
                WHERE id = ?
            """, (document_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                file_path, title, metadata_json = result
                return {
                    'file_path': file_path,
                    'title': title,
                    'metadata': json.loads(metadata_json)
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Erro ao buscar informações do documento: {e}")
            return None