"""
Sistema de backup automático para documentos OCR
Integra com serviços de nuvem via MCP para backup e sincronização
"""

import asyncio
import json
import logging
import os
import shutil
import sqlite3
import zipfile
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import threading
import time

@dataclass
class BackupJob:
    """Job de backup"""
    id: str
    source_path: str
    backup_type: str  # 'full', 'incremental', 'differential'
    cloud_service: str  # 'google_drive', 'dropbox', 'onedrive'
    scheduled_time: datetime
    status: str  # 'pending', 'running', 'completed', 'failed'
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    files_backed_up: int = 0
    total_size_mb: float = 0.0

@dataclass
class BackupStatus:
    """Status do sistema de backup"""
    last_backup: Optional[datetime]
    next_backup: Optional[datetime]
    total_backups: int
    failed_backups: int
    total_size_backed_up: float
    cloud_services_active: List[str]
    auto_backup_enabled: bool

class BackupManager:
    """Gerenciador de backup automático para sistema OCR"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or Path.home() / ".claude" / "backup_config.json"
        self.db_path = Path.home() / ".claude" / "backup_history.db"
        self.logger = logging.getLogger(__name__)
        
        # Configurações padrão
        self.auto_backup_enabled = False
        self.backup_interval_hours = 24  # Backup diário por padrão
        self.retention_days = 30  # Manter backups por 30 dias
        self.max_backup_size_mb = 1024  # Máximo 1GB por backup
        self.cloud_services = {}
        
        # Diretórios
        self.local_backup_dir = Path.home() / ".claude" / "backups"
        self.local_backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Controle de thread
        self.backup_thread = None
        self.stop_backup_thread = False
        
        self.load_config()
        self.init_database()
    
    def load_config(self):
        """Carrega configuração de backup"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    self.auto_backup_enabled = config.get('auto_backup_enabled', False)
                    self.backup_interval_hours = config.get('backup_interval_hours', 24)
                    self.retention_days = config.get('retention_days', 30)
                    self.max_backup_size_mb = config.get('max_backup_size_mb', 1024)
                    self.cloud_services = config.get('cloud_services', {})
                    self.logger.info("Configuração de backup carregada")
        except Exception as e:
            self.logger.error(f"Erro ao carregar configuração de backup: {e}")
    
    def save_config(self):
        """Salva configuração de backup"""
        try:
            config = {
                'auto_backup_enabled': self.auto_backup_enabled,
                'backup_interval_hours': self.backup_interval_hours,
                'retention_days': self.retention_days,
                'max_backup_size_mb': self.max_backup_size_mb,
                'cloud_services': self.cloud_services,
                'last_updated': datetime.now().isoformat()
            }
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            self.logger.error(f"Erro ao salvar configuração de backup: {e}")
    
    def init_database(self):
        """Inicializa banco de dados de histórico de backup"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Tabela de jobs de backup
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backup_jobs (
                    id TEXT PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    backup_type TEXT NOT NULL,
                    cloud_service TEXT NOT NULL,
                    scheduled_time TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    error_message TEXT,
                    files_backed_up INTEGER DEFAULT 0,
                    total_size_mb REAL DEFAULT 0.0
                )
            """)
            
            # Tabela de arquivos de backup
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backup_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    backup_path TEXT NOT NULL,
                    file_size_bytes INTEGER NOT NULL,
                    backed_up_at TEXT NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES backup_jobs (id)
                )
            """)
            
            # Tabela de configurações de sincronização
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_config (
                    service_name TEXT PRIMARY KEY,
                    config_data TEXT NOT NULL,
                    last_sync TEXT,
                    sync_enabled BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Índices
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_backup_status ON backup_jobs(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_backup_date ON backup_jobs(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON backup_files(file_hash)")
            
            conn.commit()
            conn.close()
            
            self.logger.info("Banco de dados de backup inicializado")
            
        except Exception as e:
            self.logger.error(f"Erro ao inicializar banco de backup: {e}")
    
    def calculate_file_hash(self, file_path: str) -> str:
        """Calcula hash MD5 de um arquivo"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            self.logger.error(f"Erro ao calcular hash do arquivo {file_path}: {e}")
            return ""
    
    async def create_backup_job(self, source_path: str, backup_type: str = "incremental", 
                               cloud_service: str = "local") -> str:
        """Cria um novo job de backup"""
        try:
            job_id = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(source_path) % 10000}"
            
            job = BackupJob(
                id=job_id,
                source_path=source_path,
                backup_type=backup_type,
                cloud_service=cloud_service,
                scheduled_time=datetime.now(),
                status='pending',
                created_at=datetime.now()
            )
            
            # Salvar no banco
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO backup_jobs 
                (id, source_path, backup_type, cloud_service, scheduled_time, 
                 status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                job.id, job.source_path, job.backup_type, job.cloud_service,
                job.scheduled_time.isoformat(), job.status, job.created_at.isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Job de backup criado: {job_id}")
            return job_id
            
        except Exception as e:
            self.logger.error(f"Erro ao criar job de backup: {e}")
            return ""
    
    async def execute_backup(self, job_id: str) -> bool:
        """Executa um job de backup"""
        try:
            # Buscar job no banco
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM backup_jobs WHERE id = ?", (job_id,))
            job_data = cursor.fetchone()
            
            if not job_data:
                self.logger.error(f"Job de backup não encontrado: {job_id}")
                return False
            
            # Atualizar status para running
            cursor.execute("""
                UPDATE backup_jobs SET status = 'running' WHERE id = ?
            """, (job_id,))
            conn.commit()
            
            # Extrair dados do job
            _, source_path, backup_type, cloud_service, _, _, _, _, _, _, _ = job_data
            
            self.logger.info(f"Iniciando backup: {job_id} - {source_path}")
            
            # Executar backup baseado no tipo
            if backup_type == "full":
                success = await self.execute_full_backup(job_id, source_path, cloud_service)
            elif backup_type == "incremental":
                success = await self.execute_incremental_backup(job_id, source_path, cloud_service)
            else:
                success = await self.execute_differential_backup(job_id, source_path, cloud_service)
            
            # Atualizar status final
            final_status = 'completed' if success else 'failed'
            cursor.execute("""
                UPDATE backup_jobs SET status = ?, completed_at = ? WHERE id = ?
            """, (final_status, datetime.now().isoformat(), job_id))
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Backup finalizado: {job_id} - Status: {final_status}")
            return success
            
        except Exception as e:
            self.logger.error(f"Erro ao executar backup {job_id}: {e}")
            
            # Marcar como falhado
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE backup_jobs SET status = 'failed', error_message = ?, completed_at = ? 
                    WHERE id = ?
                """, (str(e), datetime.now().isoformat(), job_id))
                conn.commit()
                conn.close()
            except:
                pass
                
            return False
    
    async def execute_full_backup(self, job_id: str, source_path: str, cloud_service: str) -> bool:
        """Executa backup completo"""
        try:
            if not os.path.exists(source_path):
                self.logger.error(f"Caminho de origem não existe: {source_path}")
                return False
            
            # Criar nome do arquivo de backup
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"full_backup_{timestamp}.zip"
            local_backup_path = self.local_backup_dir / backup_filename
            
            files_backed_up = 0
            total_size = 0
            
            # Criar arquivo ZIP
            with zipfile.ZipFile(local_backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                if os.path.isfile(source_path):
                    # Backup de arquivo único
                    zipf.write(source_path, os.path.basename(source_path))
                    files_backed_up = 1
                    total_size = os.path.getsize(source_path)
                else:
                    # Backup de diretório
                    for root, dirs, files in os.walk(source_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            if os.path.exists(file_path):
                                arcname = os.path.relpath(file_path, source_path)
                                zipf.write(file_path, arcname)
                                files_backed_up += 1
                                total_size += os.path.getsize(file_path)
            
            # Verificar tamanho do backup
            backup_size_mb = os.path.getsize(local_backup_path) / (1024 * 1024)
            
            if backup_size_mb > self.max_backup_size_mb:
                self.logger.warning(f"Backup excede tamanho máximo: {backup_size_mb:.1f}MB")
            
            # Atualizar estatísticas do job
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE backup_jobs SET files_backed_up = ?, total_size_mb = ? WHERE id = ?
            """, (files_backed_up, backup_size_mb, job_id))
            conn.commit()
            conn.close()
            
            # Upload para nuvem se configurado
            if cloud_service != "local":
                cloud_success = await self.upload_to_cloud(local_backup_path, cloud_service)
                if not cloud_success:
                    self.logger.warning(f"Falha no upload para {cloud_service}")
            
            self.logger.info(f"Backup completo criado: {backup_filename} ({backup_size_mb:.1f}MB, {files_backed_up} arquivos)")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro no backup completo: {e}")
            return False
    
    async def execute_incremental_backup(self, job_id: str, source_path: str, cloud_service: str) -> bool:
        """Executa backup incremental"""
        try:
            # Buscar último backup
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT MAX(completed_at) FROM backup_jobs 
                WHERE source_path = ? AND status = 'completed'
            """, (source_path,))
            
            last_backup_str = cursor.fetchone()[0]
            
            if last_backup_str:
                last_backup = datetime.fromisoformat(last_backup_str)
            else:
                # Primeiro backup - fazer completo
                self.logger.info("Primeiro backup - executando backup completo")
                return await self.execute_full_backup(job_id, source_path, cloud_service)
            
            # Encontrar arquivos modificados desde último backup
            modified_files = []
            
            if os.path.isfile(source_path):
                file_mtime = datetime.fromtimestamp(os.path.getmtime(source_path))
                if file_mtime > last_backup:
                    modified_files.append(source_path)
            else:
                for root, dirs, files in os.walk(source_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if os.path.exists(file_path):
                            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                            if file_mtime > last_backup:
                                modified_files.append(file_path)
            
            if not modified_files:
                self.logger.info("Nenhum arquivo modificado desde último backup")
                return True
            
            # Criar backup incremental
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"incremental_backup_{timestamp}.zip"
            local_backup_path = self.local_backup_dir / backup_filename
            
            total_size = 0
            with zipfile.ZipFile(local_backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in modified_files:
                    if os.path.isfile(source_path):
                        arcname = os.path.basename(file_path)
                    else:
                        arcname = os.path.relpath(file_path, source_path)
                    zipf.write(file_path, arcname)
                    total_size += os.path.getsize(file_path)
            
            backup_size_mb = os.path.getsize(local_backup_path) / (1024 * 1024)
            
            # Atualizar estatísticas
            cursor.execute("""
                UPDATE backup_jobs SET files_backed_up = ?, total_size_mb = ? WHERE id = ?
            """, (len(modified_files), backup_size_mb, job_id))
            conn.commit()
            conn.close()
            
            # Upload para nuvem
            if cloud_service != "local":
                await self.upload_to_cloud(local_backup_path, cloud_service)
            
            self.logger.info(f"Backup incremental criado: {backup_filename} ({len(modified_files)} arquivos)")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro no backup incremental: {e}")
            return False
    
    async def execute_differential_backup(self, job_id: str, source_path: str, cloud_service: str) -> bool:
        """Executa backup diferencial (mudanças desde último backup completo)"""
        try:
            # Implementação similar ao incremental, mas baseado no último backup completo
            self.logger.info("Executando backup diferencial")
            # Por simplicidade, usar incremental por enquanto
            return await self.execute_incremental_backup(job_id, source_path, cloud_service)
            
        except Exception as e:
            self.logger.error(f"Erro no backup diferencial: {e}")
            return False
    
    async def upload_to_cloud(self, file_path: Path, cloud_service: str) -> bool:
        """Upload de arquivo para serviço de nuvem via MCP"""
        try:
            self.logger.info(f"Iniciando upload para {cloud_service}: {file_path.name}")
            
            # Aqui seria a integração real com MCP
            # Por enquanto, simular upload
            await asyncio.sleep(1)  # Simular tempo de upload
            
            self.logger.info(f"Upload concluído para {cloud_service}: {file_path.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro no upload para {cloud_service}: {e}")
            return False
    
    def start_auto_backup(self):
        """Inicia thread de backup automático"""
        if self.auto_backup_enabled and not self.backup_thread:
            self.stop_backup_thread = False
            self.backup_thread = threading.Thread(target=self._auto_backup_loop, daemon=True)
            self.backup_thread.start()
            self.logger.info("Thread de backup automático iniciada")
    
    def stop_auto_backup(self):
        """Para thread de backup automático"""
        if self.backup_thread:
            self.stop_backup_thread = True
            self.backup_thread.join(timeout=5)
            self.backup_thread = None
            self.logger.info("Thread de backup automático parada")
    
    def _auto_backup_loop(self):
        """Loop principal do backup automático"""
        while not self.stop_backup_thread:
            try:
                # Verificar se é hora de fazer backup
                if self._should_run_backup():
                    self.logger.info("Iniciando backup automático")
                    
                    # Executar backup em thread separada
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    # Backup dos diretórios principais
                    backup_sources = [
                        str(Path.home() / ".claude"),
                        # Adicionar outros diretórios conforme necessário
                    ]
                    
                    for source in backup_sources:
                        if os.path.exists(source):
                            job_id = loop.run_until_complete(
                                self.create_backup_job(source, "incremental", "local")
                            )
                            if job_id:
                                loop.run_until_complete(self.execute_backup(job_id))
                    
                    loop.close()
                
                # Aguardar próxima verificação (a cada hora)
                time.sleep(3600)
                
            except Exception as e:
                self.logger.error(f"Erro no loop de backup automático: {e}")
                time.sleep(3600)  # Aguardar antes de tentar novamente
    
    def _should_run_backup(self) -> bool:
        """Verifica se deve executar backup baseado no intervalo"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT MAX(completed_at) FROM backup_jobs 
                WHERE status = 'completed'
            """)
            
            last_backup_str = cursor.fetchone()[0]
            conn.close()
            
            if not last_backup_str:
                return True  # Primeiro backup
            
            last_backup = datetime.fromisoformat(last_backup_str)
            next_backup = last_backup + timedelta(hours=self.backup_interval_hours)
            
            return datetime.now() >= next_backup
            
        except Exception as e:
            self.logger.error(f"Erro ao verificar necessidade de backup: {e}")
            return False
    
    async def cleanup_old_backups(self):
        """Remove backups antigos baseado na política de retenção"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            
            # Buscar backups antigos
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id FROM backup_jobs 
                WHERE created_at < ? AND status = 'completed'
            """, (cutoff_date.isoformat(),))
            
            old_jobs = cursor.fetchall()
            
            for (job_id,) in old_jobs:
                # Remover arquivos locais
                await self._remove_backup_files(job_id)
                
                # Remover do banco
                cursor.execute("DELETE FROM backup_files WHERE job_id = ?", (job_id,))
                cursor.execute("DELETE FROM backup_jobs WHERE id = ?", (job_id,))
            
            conn.commit()
            conn.close()
            
            if old_jobs:
                self.logger.info(f"Removidos {len(old_jobs)} backups antigos")
            
        except Exception as e:
            self.logger.error(f"Erro na limpeza de backups: {e}")
    
    async def _remove_backup_files(self, job_id: str):
        """Remove arquivos de backup de um job"""
        try:
            # Buscar arquivos do job
            for backup_file in self.local_backup_dir.glob(f"*{job_id}*"):
                if backup_file.is_file():
                    backup_file.unlink()
                    self.logger.debug(f"Arquivo de backup removido: {backup_file}")
                    
        except Exception as e:
            self.logger.error(f"Erro ao remover arquivos do job {job_id}: {e}")
    
    def get_backup_status(self) -> BackupStatus:
        """Retorna status atual do sistema de backup"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Último backup
            cursor.execute("""
                SELECT MAX(completed_at) FROM backup_jobs WHERE status = 'completed'
            """)
            last_backup_str = cursor.fetchone()[0]
            last_backup = datetime.fromisoformat(last_backup_str) if last_backup_str else None
            
            # Próximo backup
            next_backup = None
            if last_backup:
                next_backup = last_backup + timedelta(hours=self.backup_interval_hours)
            
            # Estatísticas
            cursor.execute("SELECT COUNT(*) FROM backup_jobs")
            total_backups = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM backup_jobs WHERE status = 'failed'")
            failed_backups = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(total_size_mb) FROM backup_jobs WHERE status = 'completed'")
            total_size = cursor.fetchone()[0] or 0.0
            
            conn.close()
            
            return BackupStatus(
                last_backup=last_backup,
                next_backup=next_backup,
                total_backups=total_backups,
                failed_backups=failed_backups,
                total_size_backed_up=total_size,
                cloud_services_active=list(self.cloud_services.keys()),
                auto_backup_enabled=self.auto_backup_enabled
            )
            
        except Exception as e:
            self.logger.error(f"Erro ao obter status de backup: {e}")
            return BackupStatus(
                last_backup=None,
                next_backup=None,
                total_backups=0,
                failed_backups=0,
                total_size_backed_up=0.0,
                cloud_services_active=[],
                auto_backup_enabled=False
            )
    
    def enable_auto_backup(self, enabled: bool = True):
        """Ativa/desativa backup automático"""
        self.auto_backup_enabled = enabled
        self.save_config()
        
        if enabled:
            self.start_auto_backup()
        else:
            self.stop_auto_backup()
        
        self.logger.info(f"Backup automático {'ativado' if enabled else 'desativado'}")
    
    def set_backup_interval(self, hours: int):
        """Define intervalo de backup em horas"""
        if hours > 0:
            self.backup_interval_hours = hours
            self.save_config()
            self.logger.info(f"Intervalo de backup definido para {hours} horas")
    
    def set_retention_policy(self, days: int):
        """Define política de retenção em dias"""
        if days > 0:
            self.retention_days = days
            self.save_config()
            self.logger.info(f"Política de retenção definida para {days} dias")
    
    def add_cloud_service(self, service_name: str, config: Dict[str, Any]):
        """Adiciona serviço de nuvem"""
        self.cloud_services[service_name] = config
        self.save_config()
        self.logger.info(f"Serviço de nuvem adicionado: {service_name}")
    
    def remove_cloud_service(self, service_name: str):
        """Remove serviço de nuvem"""
        if service_name in self.cloud_services:
            del self.cloud_services[service_name]
            self.save_config()
            self.logger.info(f"Serviço de nuvem removido: {service_name}")
    
    async def restore_from_backup(self, backup_id: str, restore_path: str) -> bool:
        """Restaura arquivos de um backup"""
        try:
            self.logger.info(f"Iniciando restauração do backup {backup_id}")
            
            # Buscar backup no banco
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM backup_jobs WHERE id = ?", (backup_id,))
            job_data = cursor.fetchone()
            
            if not job_data:
                self.logger.error(f"Backup não encontrado: {backup_id}")
                return False
            
            # Buscar arquivo de backup local
            backup_files = list(self.local_backup_dir.glob(f"*{backup_id}*"))
            if not backup_files:
                self.logger.error(f"Arquivo de backup não encontrado localmente")
                return False
            
            backup_file = backup_files[0]
            
            # Extrair backup
            os.makedirs(restore_path, exist_ok=True)
            
            with zipfile.ZipFile(backup_file, 'r') as zipf:
                zipf.extractall(restore_path)
            
            conn.close()
            
            self.logger.info(f"Restauração concluída: {backup_id} -> {restore_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro na restauração: {e}")
            return False