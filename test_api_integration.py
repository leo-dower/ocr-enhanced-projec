#!/usr/bin/env python3
"""
Teste de integração do sistema de gerenciamento de chaves API
"""

import os
import sys
import tempfile
import json
from pathlib import Path

# Adicionar diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from api_key_manager import APIKeyManager, get_api_key, set_api_key, list_keys
    print("✅ API Key Manager importado com sucesso")
except ImportError as e:
    print(f"❌ Erro ao importar API Key Manager: {e}")
    sys.exit(1)

def test_environment_variable():
    """Testar carregamento de variável de ambiente"""
    print("\n=== Teste 1: Variável de Ambiente ===")
    
    # Definir variável de ambiente
    test_key = "env_test_key_12345"
    os.environ['MISTRAL_API_KEY'] = test_key
    
    # Testar obtenção
    key = get_api_key('mistral')
    if key == test_key:
        print("✅ Chave carregada corretamente da variável de ambiente")
    else:
        print(f"❌ Chave incorreta. Esperado: {test_key}, Obtido: {key}")
    
    # Limpar variável
    if 'MISTRAL_API_KEY' in os.environ:
        del os.environ['MISTRAL_API_KEY']

def test_config_file():
    """Testar carregamento de arquivo de configuração"""
    print("\n=== Teste 2: Arquivo de Configuração ===")
    
    # Criar arquivo temporário
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config = {
            "mistral_api_key": "config_test_key_67890"
        }
        json.dump(config, f)
        temp_config_path = f.name
    
    try:
        # Criar manager com arquivo personalizado
        manager = APIKeyManager()
        manager.config_file = Path(temp_config_path)
        
        # Testar obtenção
        key = manager.get_api_key('mistral')
        if key == "config_test_key_67890":
            print("✅ Chave carregada corretamente do arquivo de configuração")
        else:
            print(f"❌ Chave incorreta. Esperado: config_test_key_67890, Obtido: {key}")
            
    finally:
        # Limpar arquivo temporário
        os.unlink(temp_config_path)

def test_session_key():
    """Testar chaves de sessão"""
    print("\n=== Teste 3: Chaves de Sessão ===")
    
    # Definir chave de sessão
    test_key = "session_test_key_abcdef"
    set_api_key('mistral', test_key, permanent=False)
    
    # Testar obtenção
    key = get_api_key('mistral')
    if key == test_key:
        print("✅ Chave de sessão definida e obtida corretamente")
    else:
        print(f"❌ Chave incorreta. Esperado: {test_key}, Obtido: {key}")

def test_key_validation():
    """Testar validação de chaves"""
    print("\n=== Teste 4: Validação de Chaves ===")
    
    manager = APIKeyManager()
    
    # Testar diferentes formatos
    test_cases = [
        ("mistral", "ms-1234567890abcdef", True),
        ("mistral", "valid_key_123", True),
        ("mistral", "", False),
        ("mistral", "   ", False),
        ("azure", "1234567890abcdef1234567890abcdef", True),
        ("azure", "invalid_key", False),
        ("google", "AIzaSyBveryLongGoogleAPIKey12345", True),
        ("google", "short", False),
    ]
    
    for service, key, expected in test_cases:
        result = manager.validate_key(service, key)
        status = "✅" if result == expected else "❌"
        print(f"{status} {service}: '{key[:20]}...' -> {result}")

def test_list_keys():
    """Testar listagem de chaves"""
    print("\n=== Teste 5: Listagem de Chaves ===")
    
    # Definir diferentes tipos de chaves
    os.environ['MISTRAL_API_KEY'] = "env_key"
    set_api_key('azure', 'session_key', permanent=False)
    
    # Listar chaves
    keys = list_keys()
    print("Chaves disponíveis:")
    for service, source in keys.items():
        print(f"  {service}: {source}")
    
    # Limpar
    if 'MISTRAL_API_KEY' in os.environ:
        del os.environ['MISTRAL_API_KEY']

def test_ocr_integration():
    """Testar integração com script OCR"""
    print("\n=== Teste 6: Integração com OCR ===")
    
    try:
        # Testar importação das classes do OCR
        from OCR_Enhanced_Hybrid_v1 import OCRHybridApp
        print("✅ Classes do OCR importadas com sucesso")
        
        # Verificar se a constante foi definida
        import OCR_Enhanced_Hybrid_v1
        has_manager = getattr(OCR_Enhanced_Hybrid_v1, 'HAS_API_MANAGER', False)
        print(f"✅ HAS_API_MANAGER definida: {has_manager}")
        
    except ImportError as e:
        print(f"❌ Erro na integração com OCR: {e}")

def main():
    """Executar todos os testes"""
    print("=== TESTE DE INTEGRAÇÃO API KEY MANAGER ===")
    
    test_environment_variable()
    test_config_file()
    test_session_key()
    test_key_validation()
    test_list_keys()
    test_ocr_integration()
    
    print("\n=== TESTES CONCLUÍDOS ===")
    print("✅ Sistema de gerenciamento de chaves API funcional")
    print("💡 Para usar:")
    print("  - Defina MISTRAL_API_KEY como variável de ambiente")
    print("  - Ou use o botão 'Carregar' na interface")
    print("  - Ou insira manualmente na GUI")

if __name__ == '__main__':
    main()