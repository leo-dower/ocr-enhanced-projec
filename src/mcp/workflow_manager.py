"""
Sistema de integração MCP para workflow automatizado de OCR
Gerencia conexões com servidores MCP externos para notificações, armazenamento e análise
"""

import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import subprocess
import tempfile

@dataclass
class WorkflowResult:
    """Resultado do processamento OCR para workflow"""
    file_path: str
    ocr_text: str
    confidence: float
    processing_time: float
    engine_used: str
    metadata: Dict[str, Any]
    pdf_searchable_path: Optional[str] = None
    analysis_results: Optional[Dict[str, Any]] = None

class MCPWorkflowManager:
    """Gerenciador de workflows MCP para sistema OCR"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.expanduser("~/.claude/mcp_config.json")
        self.logger = logging.getLogger(__name__)
        self.mcp_servers = {}
        self.workflow_enabled = False
        self.load_config()
    
    def load_config(self):
        """Carrega configuração dos servidores MCP"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    self.mcp_servers = config.get('mcp_servers', {})
                    self.workflow_enabled = config.get('workflow_enabled', False)
                    self.logger.info(f"Configuração MCP carregada: {len(self.mcp_servers)} servidores")
            else:
                self.logger.warning("Arquivo de configuração MCP não encontrado")
        except Exception as e:
            self.logger.error(f"Erro ao carregar configuração MCP: {e}")
    
    def save_config(self):
        """Salva configuração dos servidores MCP"""
        try:
            config = {
                'mcp_servers': self.mcp_servers,
                'workflow_enabled': self.workflow_enabled
            }
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            self.logger.error(f"Erro ao salvar configuração MCP: {e}")
    
    def add_server(self, server_name: str, server_type: str, config: Dict[str, Any]):
        """Adiciona servidor MCP à configuração"""
        self.mcp_servers[server_name] = {
            'type': server_type,
            'config': config,
            'enabled': True,
            'added_at': datetime.now().isoformat()
        }
        self.save_config()
        self.logger.info(f"Servidor MCP adicionado: {server_name} ({server_type})")
    
    def remove_server(self, server_name: str):
        """Remove servidor MCP da configuração"""
        if server_name in self.mcp_servers:
            del self.mcp_servers[server_name]
            self.save_config()
            self.logger.info(f"Servidor MCP removido: {server_name}")
    
    def enable_workflow(self, enabled: bool = True):
        """Ativa/desativa workflow automatizado"""
        self.workflow_enabled = enabled
        self.save_config()
        self.logger.info(f"Workflow automatizado {'ativado' if enabled else 'desativado'}")
    
    async def process_ocr_result(self, result: WorkflowResult) -> Dict[str, Any]:
        """Processa resultado OCR através do workflow MCP"""
        if not self.workflow_enabled:
            return {'workflow_executed': False, 'reason': 'Workflow desabilitado'}
        
        workflow_results = {
            'file_path': result.file_path,
            'timestamp': datetime.now().isoformat(),
            'steps_executed': [],
            'errors': []
        }
        
        # Passo 1: Análise de conteúdo
        if 'content_analyzer' in self.mcp_servers:
            try:
                analysis = await self._analyze_content(result)
                workflow_results['content_analysis'] = analysis
                workflow_results['steps_executed'].append('content_analysis')
            except Exception as e:
                workflow_results['errors'].append(f"Análise de conteúdo falhou: {e}")
        
        # Passo 2: Armazenamento em nuvem
        if 'cloud_storage' in self.mcp_servers:
            try:
                storage_result = await self._store_in_cloud(result)
                workflow_results['cloud_storage'] = storage_result
                workflow_results['steps_executed'].append('cloud_storage')
            except Exception as e:
                workflow_results['errors'].append(f"Armazenamento em nuvem falhou: {e}")
        
        # Passo 3: Salvar metadados em banco
        if 'database' in self.mcp_servers:
            try:
                db_result = await self._save_to_database(result, workflow_results)
                workflow_results['database'] = db_result
                workflow_results['steps_executed'].append('database')
            except Exception as e:
                workflow_results['errors'].append(f"Salvamento em banco falhou: {e}")
        
        # Passo 4: Notificações
        if 'notification' in self.mcp_servers:
            try:
                notification_result = await self._send_notifications(result, workflow_results)
                workflow_results['notification'] = notification_result
                workflow_results['steps_executed'].append('notification')
            except Exception as e:
                workflow_results['errors'].append(f"Notificação falhou: {e}")
        
        workflow_results['workflow_executed'] = True
        workflow_results['success'] = len(workflow_results['errors']) == 0
        
        return workflow_results
    
    async def _analyze_content(self, result: WorkflowResult) -> Dict[str, Any]:
        """Analisa conteúdo do OCR usando MCP"""
        server_config = self.mcp_servers.get('content_analyzer', {})
        
        # Simulação de análise - em implementação real, usaria MCP
        analysis = {
            'document_type': self._classify_document_type(result.ocr_text),
            'key_entities': self._extract_entities(result.ocr_text),
            'summary': self._generate_summary(result.ocr_text),
            'confidence': result.confidence,
            'language': self._detect_language(result.ocr_text)
        }
        
        return analysis
    
    async def _store_in_cloud(self, result: WorkflowResult) -> Dict[str, Any]:
        """Armazena arquivos em nuvem usando MCP"""
        server_config = self.mcp_servers.get('cloud_storage', {})
        
        # Simulação de upload - em implementação real, usaria MCP
        storage_result = {
            'original_file': f"cloud://documents/{os.path.basename(result.file_path)}",
            'searchable_pdf': f"cloud://documents/searchable_{os.path.basename(result.file_path)}",
            'ocr_text': f"cloud://documents/text_{os.path.basename(result.file_path)}.txt",
            'upload_time': datetime.now().isoformat(),
            'size_bytes': os.path.getsize(result.file_path) if os.path.exists(result.file_path) else 0
        }
        
        return storage_result
    
    async def _save_to_database(self, result: WorkflowResult, workflow_results: Dict[str, Any]) -> Dict[str, Any]:
        """Salva metadados em banco usando MCP"""
        server_config = self.mcp_servers.get('database', {})
        
        # Simulação de salvamento - em implementação real, usaria MCP
        db_record = {
            'file_path': result.file_path,
            'ocr_text': result.ocr_text[:1000],  # Primeiros 1000 caracteres
            'confidence': result.confidence,
            'processing_time': result.processing_time,
            'engine_used': result.engine_used,
            'metadata': result.metadata,
            'workflow_results': workflow_results,
            'created_at': datetime.now().isoformat(),
            'record_id': f"ocr_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(result.file_path) % 10000}"
        }
        
        # Indexar para busca se habilitado
        if 'search_indexer' in self.mcp_servers:
            try:
                await self._index_for_search(result)
            except Exception as e:
                self.logger.error(f"Erro ao indexar para busca: {e}")
        
        # Backup automático se habilitado
        if 'backup_manager' in self.mcp_servers:
            try:
                await self._create_backup(result)
            except Exception as e:
                self.logger.error(f"Erro ao criar backup: {e}")
        
        return {'record_id': db_record['record_id'], 'saved': True}
    
    async def _send_notifications(self, result: WorkflowResult, workflow_results: Dict[str, Any]) -> Dict[str, Any]:
        """Envia notificações usando MCP"""
        server_config = self.mcp_servers.get('notification', {})
        
        # Preparar mensagem de notificação
        success_count = len(workflow_results['steps_executed'])
        error_count = len(workflow_results['errors'])
        
        message = f"""
📄 OCR Processado: {os.path.basename(result.file_path)}
⏱️ Tempo: {result.processing_time:.2f}s
🔧 Engine: {result.engine_used}
📊 Confiança: {result.confidence:.2%}
✅ Etapas: {success_count}
❌ Erros: {error_count}
"""
        
        # Simulação de envio - em implementação real, usaria MCP
        notification_result = {
            'message': message,
            'channels': ['slack', 'email'],
            'sent_at': datetime.now().isoformat(),
            'success': True
        }
        
        return notification_result
    
    def _classify_document_type(self, text: str) -> str:
        """Classifica tipo de documento baseado no texto"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['contrato', 'acordo', 'partes']):
            return 'contrato'
        elif any(word in text_lower for word in ['sentença', 'juiz', 'processo']):
            return 'jurídico'
        elif any(word in text_lower for word in ['fatura', 'valor', 'pagamento']):
            return 'financeiro'
        elif any(word in text_lower for word in ['relatório', 'análise', 'resultado']):
            return 'relatório'
        else:
            return 'documento_geral'
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extrai entidades importantes do texto"""
        # Implementação básica - em produção usaria NLP avançado
        entities = []
        
        # Buscar datas
        import re
        date_pattern = r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}'
        dates = re.findall(date_pattern, text)
        entities.extend([f"data:{date}" for date in dates])
        
        # Buscar valores monetários
        money_pattern = r'R\$\s*\d+(?:\.\d{3})*(?:,\d{2})?'
        money = re.findall(money_pattern, text)
        entities.extend([f"valor:{val}" for val in money])
        
        return entities[:10]  # Limitar a 10 entidades
    
    def _generate_summary(self, text: str) -> str:
        """Gera resumo do texto"""
        # Implementação básica - em produção usaria LLM
        words = text.split()
        if len(words) <= 50:
            return text
        
        # Pegar primeiras e últimas frases
        sentences = text.split('.')
        if len(sentences) >= 3:
            return f"{sentences[0]}.{sentences[1]}...{sentences[-1]}"
        else:
            return ' '.join(words[:50]) + '...'
    
    def _detect_language(self, text: str) -> str:
        """Detecta idioma do texto"""
        # Implementação básica
        portuguese_words = ['de', 'da', 'do', 'para', 'com', 'por', 'que', 'não', 'uma', 'como']
        english_words = ['the', 'and', 'for', 'with', 'this', 'that', 'from', 'they', 'have', 'been']
        
        text_lower = text.lower()
        pt_count = sum(1 for word in portuguese_words if word in text_lower)
        en_count = sum(1 for word in english_words if word in text_lower)
        
        if pt_count > en_count:
            return 'português'
        elif en_count > pt_count:
            return 'inglês'
        else:
            return 'indeterminado'
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status do sistema MCP"""
        return {
            'workflow_enabled': self.workflow_enabled,
            'servers_configured': len(self.mcp_servers),
            'servers': {name: {'type': config['type'], 'enabled': config['enabled']} 
                       for name, config in self.mcp_servers.items()}
        }
    
    def setup_default_servers(self):
        """Configura servidores MCP padrão para demonstração"""
        default_servers = {
            'notification': {
                'type': 'slack',
                'config': {
                    'webhook_url': 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL',
                    'channel': '#ocr-notifications'
                },
                'enabled': False
            },
            'cloud_storage': {
                'type': 'google_drive',
                'config': {
                    'folder_id': 'YOUR_FOLDER_ID',
                    'credentials_path': '~/.config/gdrive/credentials.json'
                },
                'enabled': False
            },
            'database': {
                'type': 'postgresql',
                'config': {
                    'host': 'localhost',
                    'port': 5432,
                    'database': 'ocr_workflow',
                    'user': 'ocr_user',
                    'password': 'your_password'
                },
                'enabled': False
            },
            'content_analyzer': {
                'type': 'openai',
                'config': {
                    'api_key': 'sk-your-openai-key',
                    'model': 'gpt-4'
                },
                'enabled': False
            },
            'search_indexer': {
                'type': 'elasticsearch',
                'config': {
                    'host': 'localhost',
                    'port': 9200,
                    'index_name': 'ocr_documents'
                },
                'enabled': True
            },
            'backup_manager': {
                'type': 'cloud_backup',
                'config': {
                    'auto_backup': True,
                    'interval_hours': 24,
                    'retention_days': 30
                },
                'enabled': True
            }
        }
        
        self.mcp_servers = default_servers
        self.save_config()
        self.logger.info("Servidores MCP padrão configurados")
    
    async def _index_for_search(self, result: WorkflowResult):
        """Indexa documento para busca inteligente"""
        try:
            # Importar SearchManager localmente para evitar dependência circular
            from .search_manager import SearchManager
            
            # Converter WorkflowResult para formato OCR
            ocr_result = {
                'pages': [{'content': result.ocr_text, 'confidence': result.confidence}],
                'metadata': result.metadata
            }
            
            # Criar instância do SearchManager
            search_manager = SearchManager()
            
            # Indexar documento
            await search_manager.index_document(ocr_result, result.file_path)
            
            self.logger.info(f"Documento indexado para busca: {result.file_path}")
            
        except Exception as e:
            self.logger.error(f"Erro ao indexar para busca: {e}")
            raise
    
    async def _create_backup(self, result: WorkflowResult):
        """Cria backup do documento processado"""
        try:
            # Importar BackupManager localmente para evitar dependência circular
            from .backup_manager import BackupManager
            
            # Criar instância do BackupManager
            backup_manager = BackupManager()
            
            # Criar job de backup para o arquivo processado
            job_id = await backup_manager.create_backup_job(
                source_path=result.file_path,
                backup_type="incremental",
                cloud_service="local"  # Por padrão, usar backup local
            )
            
            if job_id:
                # Executar backup em background
                await backup_manager.execute_backup(job_id)
                self.logger.info(f"Backup criado para documento: {result.file_path}")
            
        except Exception as e:
            self.logger.error(f"Erro ao criar backup: {e}")
            raise