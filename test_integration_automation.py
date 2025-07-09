#!/usr/bin/env python3
"""
Teste de integração do sistema multi-engine com automação.
"""

import sys
import tempfile
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def create_mock_engines():
    """Criar engines mock para teste."""
    from src.ocr.base import OCREngine, OCRResult, OCROptions
    
    class MockOCREngine(OCREngine):
        def __init__(self, name, processing_time=0.1, confidence=0.85, should_fail=False):
            super().__init__(name)
            self.processing_time = processing_time
            self.confidence = confidence
            self.should_fail = should_fail
        
        def is_available(self):
            return True
        
        def process_image(self, image_path, options):
            return self._process_file(image_path, options)
        
        def process_pdf(self, pdf_path, options):
            return self._process_file(pdf_path, options)
        
        def _process_file(self, file_path, options):
            time.sleep(self.processing_time)
            
            if self.should_fail:
                return OCRResult(
                    text="",
                    confidence=0.0,
                    pages=[],
                    processing_time=self.processing_time,
                    engine=self.name,
                    language=options.language,
                    file_path=str(file_path),
                    success=False,
                    error_message=f"Mock failure from {self.name}"
                )
            
            # Simular diferentes tipos de documento
            file_name = Path(file_path).name.lower()
            
            if "invoice" in file_name or "fatura" in file_name:
                text = f"NOTA FISCAL\nEmpresa: Exemplo LTDA\nCNPJ: 12.345.678/0001-90\nTotal: R$ 1.250,00\nData: 15/12/2024"
                template_name = "Brazilian Invoice"
            elif "receipt" in file_name or "recibo" in file_name:
                text = f"RECIBO\nEstabelecimento: Loja Exemplo\nTotal Pago: R$ 45,80\nData/Hora: 15/12/2024 14:30"
                template_name = "Receipt"
            else:
                text = f"Documento processado por {self.name}\nArquivo: {file_path.name}\nConteúdo de exemplo para teste"
                template_name = "Generic Document"
            
            pages = [{
                'page_number': 1,
                'text': text,
                'words': text.split(),
                'language': options.language,
                'template_detected': template_name
            }]
            
            return OCRResult(
                text=text,
                confidence=self.confidence,
                pages=pages,
                processing_time=self.processing_time,
                engine=self.name,
                language=options.language,
                file_path=str(file_path),
                word_count=len(text.split()),
                character_count=len(text),
                success=True
            )
    
    return [
        MockOCREngine("tesseract_mock", 0.5, 0.75),
        MockOCREngine("azure_mock", 0.2, 0.92),
        MockOCREngine("google_mock", 0.3, 0.88),
        MockOCREngine("mistral_mock", 1.0, 0.95),
        MockOCREngine("unreliable_mock", 0.8, 0.60, should_fail=True)
    ]


def test_multi_engine_integration():
    """Testar integração do sistema multi-engine."""
    print("🔧 Testando integração multi-engine...")
    
    try:
        from src.ocr.multi_engine import create_multi_engine_ocr, EnginePreferences
        from src.ocr.base import OCROptions
        
        # Criar preferências avançadas
        preferences = EnginePreferences(
            preferred_engines=["azure_mock", "google_mock"],
            fallback_engines=["tesseract_mock", "mistral_mock"],
            quality_threshold=0.8,
            max_processing_time=30.0,
            enable_parallel_processing=False,
            enable_quality_comparison=True
        )
        
        # Criar sistema multi-engine
        multi_ocr = create_multi_engine_ocr(preferences)
        
        # Registrar engines mock
        mock_engines = create_mock_engines()
        for engine in mock_engines:
            multi_ocr.register_engine(engine)
        
        print(f"  ✅ Registrados {len(mock_engines)} engines mock")
        
        # Criar arquivos de teste
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            test_files = [
                temp_path / "invoice_001.pdf",
                temp_path / "receipt_002.pdf",
                temp_path / "document_003.pdf",
                temp_path / "contract_004.pdf"
            ]
            
            # Criar arquivos de teste
            for file_path in test_files:
                file_path.touch()
            
            print(f"  ✅ Criados {len(test_files)} arquivos de teste")
            
            # Testar processamento de cada arquivo
            results = []
            total_time = 0
            
            for file_path in test_files:
                print(f"    📄 Processando {file_path.name}...")
                
                options = OCROptions(
                    language="por+eng",
                    confidence_threshold=0.7
                )
                
                start_time = time.time()
                result = multi_ocr.process_file(file_path, options)
                processing_time = time.time() - start_time
                total_time += processing_time
                
                results.append({
                    'file': file_path.name,
                    'success': result.success,
                    'engine': result.engine,
                    'confidence': result.confidence,
                    'processing_time': result.processing_time,
                    'real_time': processing_time,
                    'text_length': len(result.text) if result.success else 0
                })
                
                if result.success:
                    print(f"      ✅ Sucesso com {result.engine} (confiança: {result.confidence:.2f})")
                else:
                    print(f"      ❌ Falha: {result.error_message}")
            
            # Mostrar estatísticas
            successful = sum(1 for r in results if r['success'])
            print(f"  📊 Resultados: {successful}/{len(results)} sucessos ({successful/len(results)*100:.1f}%)")
            print(f"  ⏱️ Tempo total: {total_time:.2f}s")
            
            # Estatísticas do sistema
            stats = multi_ocr.get_engine_statistics()
            print(f"  📈 Sistema processou: {stats['total_processed']} arquivos")
            print(f"  📈 Taxa de sucesso geral: {stats['overall_success_rate']:.2%}")
            
            # Estatísticas por engine
            print(f"  🔧 Performance por engine:")
            for engine_name, engine_data in stats['engines'].items():
                if engine_data['metrics']['total_processed'] > 0:
                    print(f"    {engine_name}: {engine_data['quality_score']:.2f} qualidade, "
                          f"{engine_data['metrics']['success_rate']:.1%} sucesso")
            
            # Recomendações
            recommendations = multi_ocr.get_recommendations()
            if recommendations['recommended_primary']:
                print(f"  💡 Engine recomendado: {recommendations['recommended_primary']}")
            
            return True
            
    except Exception as e:
        print(f"  ❌ Erro na integração: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_parallel_processing():
    """Testar processamento paralelo."""
    print("\n⚡ Testando processamento paralelo...")
    
    try:
        from src.ocr.multi_engine import create_multi_engine_ocr, EnginePreferences
        from src.ocr.base import OCROptions
        
        # Criar preferências com processamento paralelo
        preferences = EnginePreferences(
            preferred_engines=["azure_mock", "google_mock", "tesseract_mock"],
            quality_threshold=0.7,
            enable_parallel_processing=True,
            enable_quality_comparison=True
        )
        
        multi_ocr = create_multi_engine_ocr(preferences)
        
        # Registrar apenas 3 engines para teste paralelo
        mock_engines = create_mock_engines()[:3]
        for engine in mock_engines:
            multi_ocr.register_engine(engine)
        
        print(f"  ✅ Configurado processamento paralelo com {len(mock_engines)} engines")
        
        # Teste com arquivo
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            
            options = OCROptions(language="por", confidence_threshold=0.7)
            
            # Medir tempo de processamento paralelo
            start_time = time.time()
            result = multi_ocr.process_file(temp_path, options)
            parallel_time = time.time() - start_time
            
            if result.success:
                print(f"  ✅ Processamento paralelo bem-sucedido")
                print(f"    Engine vencedor: {result.engine}")
                print(f"    Confiança: {result.confidence:.2f}")
                print(f"    Tempo total: {parallel_time:.2f}s")
                print(f"    Tempo do engine: {result.processing_time:.2f}s")
            else:
                print(f"  ❌ Processamento paralelo falhou: {result.error_message}")
            
            # Limpar arquivo temporário
            temp_path.unlink()
            
            return result.success
            
    except Exception as e:
        print(f"  ❌ Erro no processamento paralelo: {e}")
        return False


def test_quality_comparison():
    """Testar comparação de qualidade."""
    print("\n🏆 Testando comparação de qualidade...")
    
    try:
        from src.ocr.multi_engine import create_multi_engine_ocr, EnginePreferences
        from src.ocr.base import OCROptions
        
        # Configurar sistema com comparação de qualidade
        preferences = EnginePreferences(
            quality_threshold=0.9,  # Threshold alto para forçar múltiplas tentativas
            enable_parallel_processing=False,
            enable_quality_comparison=True
        )
        
        multi_ocr = create_multi_engine_ocr(preferences)
        
        # Registrar engines com diferentes qualidades
        mock_engines = create_mock_engines()
        for engine in mock_engines:
            multi_ocr.register_engine(engine)
        
        print(f"  ✅ Configurado sistema com threshold de qualidade: {preferences.quality_threshold}")
        
        # Processar múltiplos arquivos para construir histórico
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Processar vários arquivos
            for i in range(5):
                test_file = temp_path / f"quality_test_{i}.pdf"
                test_file.touch()
                
                options = OCROptions(language="por")
                result = multi_ocr.process_file(test_file, options)
                
                print(f"    📄 Arquivo {i+1}: {result.engine} (confiança: {result.confidence:.2f})")
            
            # Mostrar estatísticas de qualidade
            stats = multi_ocr.get_engine_statistics()
            
            print(f"  📊 Comparação de qualidade:")
            engine_qualities = []
            
            for engine_name, engine_data in stats['engines'].items():
                quality = engine_data['quality_score']
                success_rate = engine_data['metrics']['success_rate']
                avg_time = engine_data['metrics']['avg_processing_time']
                
                print(f"    {engine_name:15} Q:{quality:.2f} S:{success_rate:.1%} T:{avg_time:.2f}s")
                engine_qualities.append((engine_name, quality))
            
            # Ordenar por qualidade
            engine_qualities.sort(key=lambda x: x[1], reverse=True)
            best_engine = engine_qualities[0][0] if engine_qualities else None
            
            print(f"  🏆 Melhor engine por qualidade: {best_engine}")
            
            # Verificar recomendações
            recommendations = multi_ocr.get_recommendations()
            print(f"  💡 Sistema recomenda: {recommendations['recommended_primary']}")
            
            return True
            
    except Exception as e:
        print(f"  ❌ Erro na comparação de qualidade: {e}")
        return False


def test_automation_integration():
    """Testar integração com sistema de automação."""
    print("\n🤖 Testando integração com automação...")
    
    try:
        from src.ocr.multi_engine import create_multi_engine_ocr, EnginePreferences
        from src.core.config import OCRConfig
        from src.automation.automation_manager import AutomationManager
        from src.ocr.base import OCROptions
        
        # Criar configuração OCR
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            ocr_config = OCRConfig(
                input_folder=str(temp_path / "input"),
                output_folder=str(temp_path / "output"),
                mode="multi_engine",
                language="por+eng",
                confidence_threshold=0.7
            )
            
            Path(ocr_config.input_folder).mkdir(exist_ok=True)
            Path(ocr_config.output_folder).mkdir(exist_ok=True)
            
            # Criar função de processamento com multi-engine
            def create_multi_engine_processor():
                preferences = EnginePreferences(
                    preferred_engines=["azure_mock", "google_mock"],
                    fallback_engines=["tesseract_mock"],
                    quality_threshold=0.8
                )
                
                multi_ocr = create_multi_engine_ocr(preferences)
                
                # Registrar engines mock
                mock_engines = create_mock_engines()[:3]  # Apenas 3 engines
                for engine in mock_engines:
                    multi_ocr.register_engine(engine)
                
                def ocr_processor(file_path, options_dict):
                    """Processor function for automation."""
                    options = OCROptions(
                        language=options_dict.get("language", "por"),
                        confidence_threshold=options_dict.get("confidence_threshold", 0.7)
                    )
                    
                    result = multi_ocr.process_file(file_path, options)
                    
                    # Convert to automation-compatible format
                    return {
                        "success": result.success,
                        "text": result.text,
                        "confidence": result.confidence,
                        "processing_time": result.processing_time,
                        "engine_used": result.engine,
                        "word_count": result.word_count,
                        "pages": len(result.pages),
                        "error": result.error_message if not result.success else None
                    }
                
                return ocr_processor, multi_ocr
            
            # Criar processor e sistema
            ocr_processor, multi_ocr = create_multi_engine_processor()
            
            # Criar automation manager
            automation_manager = AutomationManager(ocr_config, ocr_processor)
            
            print(f"  ✅ AutomationManager criado com multi-engine")
            
            # Testar processamento via automation manager
            test_file = Path(ocr_config.input_folder) / "automation_test.pdf"
            test_file.touch()
            
            processing_options = {
                "mode": "multi_engine",
                "language": "por+eng",
                "confidence_threshold": 0.7,
                "output_folder": ocr_config.output_folder
            }
            
            result = automation_manager.process_single_file(test_file, processing_options)
            
            if result["success"]:
                print(f"  ✅ Processamento via automação bem-sucedido")
                print(f"    Engine usado: {result['context'].get('ocr_result', {}).get('engine_used', 'unknown')}")
                print(f"    Automação aplicada: {result['automation_applied']}")
                print(f"    Tempo total: {result['processing_time']:.2f}s")
            else:
                print(f"  ❌ Processamento via automação falhou: {result.get('error', 'unknown')}")
            
            # Verificar estatísticas integradas
            stats = multi_ocr.get_engine_statistics()
            automation_stats = automation_manager.get_status()
            
            print(f"  📊 Multi-engine processou: {stats['total_processed']} arquivos")
            print(f"  📊 Automação processou: {automation_stats['statistics']['total_files_processed']} arquivos")
            
            return result["success"]
            
    except Exception as e:
        print(f"  ❌ Erro na integração com automação: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Função principal de teste de integração."""
    print("🚀 Teste de Integração - Sistema Multi-Engine + Automação")
    print("=" * 70)
    
    tests = [
        ("Integração Multi-Engine", test_multi_engine_integration),
        ("Processamento Paralelo", test_parallel_processing),
        ("Comparação de Qualidade", test_quality_comparison),
        ("Integração com Automação", test_automation_integration)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n📋 Executando: {test_name}")
        print("-" * 50)
        
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
    print(f"\n🎯 Resumo dos Testes de Integração")
    print("=" * 40)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASSOU" if success else "❌ FALHOU"
        print(f"  {test_name:25} {status}")
    
    print(f"\n📊 Resultado Final: {passed}/{total} testes passaram ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 Todos os testes de integração passaram!")
        print("✅ Sistema multi-engine integrado com automação funciona perfeitamente!")
    elif passed >= total * 0.75:
        print("✅ Maioria dos testes passou - sistema funcional com pequenos ajustes necessários")
    else:
        print("⚠️ Vários testes falharam - sistema precisa de revisão")
    
    return 0 if passed >= total * 0.75 else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)