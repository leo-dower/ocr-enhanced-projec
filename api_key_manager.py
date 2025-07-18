#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API Key Manager - Sistema simples de gerenciamento de chaves API
Foco em funcionalidade e segurança com dependências mínimas
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict
import getpass

class APIKeyManager:
    """
    Gerenciador de chaves API com hierarquia de fallback:
    1. Variáveis de ambiente (maior prioridade)
    2. Arquivo de configuração local
    3. Entrada manual do usuário
    """
    
    def __init__(self):
        self.config_file = Path.home() / '.ocr-api-keys.json'
        self.session_keys = {}  # Chaves temporárias da sessão
        
    def get_api_key(self, service: str = 'mistral') -> Optional[str]:
        """
        Obter chave API com fallback hierárquico
        
        Args:
            service: Nome do serviço ('mistral', 'azure', 'google')
            
        Returns:
            Chave API ou None se não encontrada
        """
        # 1. Verificar variáveis de ambiente primeiro
        env_key = self._get_from_environment(service)
        if env_key:
            return env_key
            
        # 2. Verificar arquivo de configuração
        config_key = self._get_from_config_file(service)
        if config_key:
            return config_key
            
        # 3. Verificar chaves da sessão
        if service in self.session_keys:
            return self.session_keys[service]
            
        # 4. Solicitar entrada manual
        return self._prompt_for_key(service)
    
    def _get_from_environment(self, service: str) -> Optional[str]:
        """Obter chave de variável de ambiente"""
        env_vars = {
            'mistral': 'MISTRAL_API_KEY',
            'azure': 'AZURE_VISION_KEY',
            'google': 'GOOGLE_VISION_KEY'
        }
        
        env_var = env_vars.get(service)
        if env_var:
            return os.getenv(env_var)
        return None
    
    def _get_from_config_file(self, service: str) -> Optional[str]:
        """Obter chave do arquivo de configuração"""
        try:
            if self.config_file.exists():
                # Definir permissões seguras no arquivo
                os.chmod(self.config_file, 0o600)
                
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get(f'{service}_api_key')
        except Exception:
            pass
        return None
    
    def _prompt_for_key(self, service: str) -> Optional[str]:
        """Solicitar chave do usuário via terminal"""
        try:
            print(f"\n🔑 Chave API para {service.upper()} não encontrada")
            print("Você pode:")
            print(f"  1. Definir variável de ambiente: {service.upper()}_API_KEY")
            print(f"  2. Salvar em arquivo: {self.config_file}")
            print("  3. Inserir agora (temporário)")
            print("  4. Pular (pressione Enter)")
            
            key = getpass.getpass(f"Digite sua chave API {service}: ").strip()
            
            if key:
                # Armazenar na sessão
                self.session_keys[service] = key
                
                # Perguntar se quer salvar permanentemente
                save_choice = input("Salvar permanentemente? (s/N): ").lower()
                if save_choice in ['s', 'sim', 'y', 'yes']:
                    self.save_key_to_config(service, key)
                
                return key
                
        except KeyboardInterrupt:
            print("\nOperação cancelada pelo usuário")
        except Exception as e:
            print(f"Erro ao solicitar chave: {e}")
        
        return None
    
    def save_key_to_config(self, service: str, key: str) -> bool:
        """Salvar chave no arquivo de configuração"""
        try:
            # Carregar configuração existente
            config = {}
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            # Atualizar com nova chave
            config[f'{service}_api_key'] = key
            
            # Salvar com permissões seguras
            self.config_file.parent.mkdir(exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            
            # Definir permissões restritivas
            os.chmod(self.config_file, 0o600)
            
            print(f"✅ Chave salva em: {self.config_file}")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao salvar chave: {e}")
            return False
    
    def set_session_key(self, service: str, key: str):
        """Definir chave temporária da sessão"""
        self.session_keys[service] = key
    
    def list_available_keys(self) -> Dict[str, str]:
        """Listar fontes de chaves disponíveis (sem expor valores)"""
        result = {}
        services = ['mistral', 'azure', 'google']
        
        for service in services:
            sources = []
            
            if self._get_from_environment(service):
                sources.append("environment")
            if self._get_from_config_file(service):
                sources.append("config_file")
            if service in self.session_keys:
                sources.append("session")
            
            if sources:
                result[service] = ", ".join(sources)
            else:
                result[service] = "not_found"
        
        return result
    
    def validate_key(self, service: str, key: str) -> bool:
        """Validar formato básico da chave API"""
        if not key or not key.strip():
            return False
            
        # Validações básicas por serviço
        if service == 'mistral':
            # Mistral API keys geralmente começam com 'ms-'
            return len(key) > 10 and key.replace('-', '').replace('_', '').isalnum()
        elif service == 'azure':
            # Azure keys são geralmente hexadecimais de 32 caracteres
            return len(key) == 32 and all(c in '0123456789abcdefABCDEF' for c in key)
        elif service == 'google':
            # Google API keys são strings alfanuméricas longas
            return len(key) > 20 and key.replace('-', '').replace('_', '').isalnum()
        
        return True  # Aceitar outros formatos
    
    def clear_session_keys(self):
        """Limpar chaves temporárias da sessão"""
        self.session_keys.clear()
    
    def remove_config_file(self):
        """Remover arquivo de configuração"""
        try:
            if self.config_file.exists():
                self.config_file.unlink()
                print(f"✅ Arquivo de configuração removido: {self.config_file}")
                return True
        except Exception as e:
            print(f"❌ Erro ao remover arquivo: {e}")
        return False

# Instância global para facilitar uso
api_key_manager = APIKeyManager()

# Funções de conveniência
def get_api_key(service: str = 'mistral') -> Optional[str]:
    """Função de conveniência para obter chave API"""
    return api_key_manager.get_api_key(service)

def set_api_key(service: str, key: str, permanent: bool = False):
    """Função de conveniência para definir chave API"""
    if permanent:
        api_key_manager.save_key_to_config(service, key)
    else:
        api_key_manager.set_session_key(service, key)

def list_keys() -> Dict[str, str]:
    """Função de conveniência para listar chaves disponíveis"""
    return api_key_manager.list_available_keys()

if __name__ == '__main__':
    # Teste básico
    print("=== API Key Manager Test ===")
    
    # Listar chaves disponíveis
    keys = list_keys()
    print("\nChaves disponíveis:")
    for service, source in keys.items():
        print(f"  {service}: {source}")
    
    # Teste de obtenção de chave
    print("\nTeste de obtenção de chave Mistral:")
    key = get_api_key('mistral')
    if key:
        print(f"✅ Chave obtida (primeiros 10 chars): {key[:10]}...")
    else:
        print("❌ Nenhuma chave encontrada")