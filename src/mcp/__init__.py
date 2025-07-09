"""
Módulo de integração MCP (Model Context Protocol) para workflow automatizado
"""

from .workflow_manager import MCPWorkflowManager, WorkflowResult
from .search_manager import SearchManager, SearchResult, DocumentIndex
from .semantic_search import SemanticSearchEngine, SemanticResult
from .backup_manager import BackupManager, BackupJob, BackupStatus

__all__ = ['MCPWorkflowManager', 'WorkflowResult', 'SearchManager', 'SearchResult', 'DocumentIndex', 'SemanticSearchEngine', 'SemanticResult', 'BackupManager', 'BackupJob', 'BackupStatus']