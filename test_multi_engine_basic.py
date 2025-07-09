#!/usr/bin/env python3
"""
Teste básico do sistema multi-engine OCR.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """Testar imports básicos."""
    print("🧪 Testando imports básicos...")
    
    try:
        from src.utils.logger import get_logger
        print("  ✅ Logger import OK")
    except ImportError as e:
        print(f"  ❌ Logger import failed: {e}")
        return False
    
    try:
        from src.ocr.base import OCREngine, OCRResult, OCROptions, OCREngineManager
        print("  ✅ OCR base classes OK")
    except ImportError as e:
        print(f"  ❌ OCR base import failed: {e}")
        return False
    
    try:
        from src.ocr.multi_engine import MultiEngineOCR, EnginePreferences
        print("  ✅ Multi-engine import OK")
    except ImportError as e:
        print(f"  ❌ Multi-engine import failed: {e}")
        return False
    
    return True


def test_basic_functionality():
    """Testar funcionalidade básica."""
    print("\n🔧 Testando funcionalidade básica...")
    
    try:
        from src.ocr.multi_engine import create_multi_engine_ocr, EnginePreferences
        from src.ocr.base import OCROptions
        
        # Criar preferências
        preferences = EnginePreferences(
            preferred_engines=["tesseract"],
            quality_threshold=0.7,
            enable_parallel_processing=False
        )
        print("  ✅ EnginePreferences criado")
        
        # Criar sistema multi-engine
        multi_ocr = create_multi_engine_ocr(preferences)
        print("  ✅ MultiEngineOCR criado")
        
        # Testar sem engines registrados
        stats = multi_ocr.get_engine_statistics()
        print(f"  ✅ Estatísticas: {stats['total_processed']} processados")
        
        recommendations = multi_ocr.get_recommendations()
        print(f"  ✅ Recomendações: {len(recommendations)} itens")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Erro na funcionalidade básica: {e}")
        return False


def test_engine_availability():
    """Testar disponibilidade de engines."""
    print("\n🔍 Testando disponibilidade de engines...")
    
    try:
        from src.ocr import get_available_engines
        
        available = get_available_engines()
        print(f"  📊 Engines disponíveis:")
        
        for engine, is_available in available.items():
            status = "✅ Disponível" if is_available else "❌ Não disponível"
            print(f"    {engine:15} {status}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Erro verificando engines: {e}")
        return False


def test_cloud_engines():
    """Testar engines de nuvem (imports apenas)."""
    print("\n☁️ Testando engines de nuvem (imports)...")
    
    # Azure
    try:
        from src.ocr.azure_vision import AzureVisionEngine
        print("  🔵 Azure Vision engine - import OK")
        
        # Teste básico sem credenciais
        engine = AzureVisionEngine("dummy", "dummy")
        print(f"    Engine name: {engine.name}")
        print(f"    Available: {engine.is_available()}")  # Deve retornar False
        
    except ImportError as e:
        print(f"  🔵 Azure Vision engine - não disponível: {e}")
    except Exception as e:
        print(f"  🔵 Azure Vision engine - erro: {e}")
    
    # Google
    try:
        from src.ocr.google_vision import GoogleVisionEngine
        print("  🟢 Google Vision engine - import OK")
        
        # Teste básico sem credenciais
        engine = GoogleVisionEngine()
        print(f"    Engine name: {engine.name}")
        print(f"    Available: {engine.is_available()}")  # Deve retornar False
        
    except ImportError as e:
        print(f"  🟢 Google Vision engine - não disponível: {e}")
    except Exception as e:
        print(f"  🟢 Google Vision engine - erro: {e}")
    
    return True


def test_mock_engine():
    """Criar e testar um engine mock."""
    print("\n🎭 Testando com engine mock...")
    
    try:
        from src.ocr.base import OCREngine, OCRResult, OCROptions
        from src.ocr.multi_engine import create_multi_engine_ocr
        import time
        
        # Criar engine mock
        class MockOCREngine(OCREngine):
            def __init__(self, name="mock", should_work=True):
                super().__init__(name)
                self.should_work = should_work
            
            def is_available(self):
                return True
            
            def process_image(self, image_path, options):
                return self._create_mock_result(image_path, options)
            
            def process_pdf(self, pdf_path, options):
                return self._create_mock_result(pdf_path, options)
            
            def _create_mock_result(self, file_path, options):
                time.sleep(0.1)  # Simular processamento
                
                if self.should_work:
                    return OCRResult(
                        text=f"Texto extraído de {Path(file_path).name} pelo {self.name}",
                        confidence=0.85,
                        pages=[{
                            'page_number': 1,
                            'text': f"Conteúdo da página de {Path(file_path).name}",
                            'words': [],
                            'language': options.language
                        }],
                        processing_time=0.1,
                        engine=self.name,
                        language=options.language,
                        file_path=str(file_path),
                        word_count=5,
                        character_count=50,
                        success=True
                    )
                else:
                    return OCRResult(
                        text="",
                        confidence=0.0,
                        pages=[],
                        processing_time=0.1,
                        engine=self.name,
                        language=options.language,
                        file_path=str(file_path),
                        success=False,
                        error_message="Mock engine error"
                    )
        
        # Criar multi-engine e registrar mocks
        multi_ocr = create_multi_engine_ocr()
        
        mock1 = MockOCREngine("mock_fast", True)
        mock2 = MockOCREngine("mock_slow", True)
        mock3 = MockOCREngine("mock_fail", False)
        
        multi_ocr.register_engine(mock1)
        multi_ocr.register_engine(mock2)
        multi_ocr.register_engine(mock3)
        
        print("  ✅ Engines mock registrados")
        
        # Criar arquivo de teste fictício
        test_file = Path("/tmp/test_doc.pdf")
        test_file.touch()  # Criar arquivo vazio
        
        # Testar processamento
        options = OCROptions(language="por", confidence_threshold=0.7)
        result = multi_ocr.process_file(test_file, options)
        
        if result.success:
            print(f"  ✅ Processamento bem-sucedido com {result.engine}")
            print(f"    Confiança: {result.confidence:.2f}")
            print(f"    Tempo: {result.processing_time:.2f}s")
            print(f"    Texto: {result.text[:50]}...")
        else:
            print(f"  ❌ Processamento falhou: {result.error_message}")
        
        # Testar estatísticas
        stats = multi_ocr.get_engine_statistics()
        print(f"  📊 Total processado: {stats['total_processed']}")
        print(f"  📊 Taxa de sucesso: {stats['overall_success_rate']:.2%}")
        
        # Testar recomendações
        recommendations = multi_ocr.get_recommendations()
        if recommendations['recommended_primary']:
            print(f"  💡 Engine recomendado: {recommendations['recommended_primary']}")
        
        # Limpar arquivo de teste
        test_file.unlink()
        
        return True
        
    except Exception as e:
        print(f"  ❌ Erro no teste mock: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Função principal de teste."""
    print("🚀 Teste Básico do Sistema Multi-Engine OCR")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Funcionalidade Básica", test_basic_functionality),
        ("Disponibilidade de Engines", test_engine_availability),
        ("Engines de Nuvem", test_cloud_engines),
        ("Engine Mock", test_mock_engine)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n📋 Executando: {test_name}")
        print("-" * 40)
        
        try:
            success = test_func()
            results.append((test_name, success))
            
            if success:
                print(f"✅ {test_name} - SUCESSO")
            else:
                print(f"❌ {test_name} - FALHA")
                
        except Exception as e:
            print(f"❌ {test_name} - ERRO: {e}")
            results.append((test_name, False))
    
    # Resumo final
    print("\n🎯 Resumo dos Testes")
    print("=" * 30)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASSOU" if success else "❌ FALHOU"
        print(f"  {test_name:25} {status}")
    
    print(f"\n📊 Resultado Final: {passed}/{total} testes passaram ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 Todos os testes passaram! Sistema funcionando corretamente.")
        return 0
    else:
        print("⚠️ Alguns testes falharam. Verifique os erros acima.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)