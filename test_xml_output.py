#!/usr/bin/env python3
"""
Teste do gerador XML para documentos jurídicos
"""

import json
import datetime
from src.utils.xml_output_generator import XMLOutputGenerator, gerar_xml_juridico


def criar_resultado_ocr_exemplo():
    """Cria um resultado OCR de exemplo para testar o gerador XML"""
    resultado = {
        "pages": [
            {
                "page_number": 1,
                "text": """
EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA 1ª VARA CÍVEL DA COMARCA DE CUIABÁ - MT

PROCESSO NÚMERO: 0026873-09.2015.8.11.0041
REQUERENTE: TETRANS TRANSPORTES LTDA
ADMINISTRADOR: PAULO ROBERTO BRESCOVICI - OAB/MT 3.801

RELATÓRIO DO ADMINISTRADOR JUDICIAL

O administrador judicial vem apresentar relatório sobre a situação atual da recuperação judicial.

HISTÓRICO:
- 08/06/2015: Pedido de recuperação judicial pelas empresas TETRANS
- 15/07/2015: Deferimento do processamento da recuperação judicial
- 20/08/2015: Nomeação do administrador judicial

SITUAÇÃO ATUAL:
As empresas encontram-se em completo abandono e omissão, com passivo de R$ 32.382.792,48 e ativo não arrecadado.

IRRESIGNAÇÕES:
1. Irresignação 180047750:
   - Credor corrigido: CLEMENTE & DOMESI ADVOGADOS ASSOCIADOS - R$ 23.798,71 - TRABALHISTA
   - Novo credor: MITSUI SUMITOMO SEGUROS S.A. - R$ 237.987,13 - QUIROGRAFÁRIO

PEDIDOS:
1. Recebimento do presente relatório
2. Homologação de substabelecimento da CEF
3. Prosseguimento do feito
                """,
                "confidence": 0.95,
                "source_part": "part_001"
            },
            {
                "page_number": 2,
                "text": """
QUADRO GERAL DE CREDORES

ITEM    CREDOR                          VALOR           CLASSIFICAÇÃO
1       BANCO CNH CAPITAL              1.085.532,86     GARANTIA REAL
2       CAIXA ECONÔMICA FEDERAL        2.500.000,00     GARANTIA REAL
3       BANCO DO BRASIL S.A.           1.800.000,00     GARANTIA REAL
4       CLEMENTE & DOMESI ADVOGADOS      23.798,71       TRABALHISTA
5       JOÃO SILVA SANTOS               15.000,00       TRABALHISTA
6       MARIA OLIVEIRA COSTA            12.500,00       TRABALHISTA
7       FORNECEDOR ABC LTDA             350.000,00      QUIROGRAFÁRIO
8       EMPRESA XYZ S.A.                180.000,00      QUIROGRAFÁRIO
9       RECEITA FEDERAL                 800.000,00      TRIBUTÁRIO
10      PREFEITURA MUNICIPAL            125.000,00      TRIBUTÁRIO

TOTAL GERAL: R$ 6.891.831,57

Cuiabá, 02 de julho de 2025.

PAULO ROBERTO BRESCOVICI
Administrador Judicial
OAB/MT 3.801
                """,
                "confidence": 0.92,
                "source_part": "part_002"
            }
        ],
        "metadata": {
            "method": "mistral_cloud",
            "average_confidence": 0.935,
            "processing_time": 45.2,
            "language": "portuguese",
            "total_pages": 2,
            "characters_extracted": 1850,
            "processed_at": datetime.datetime.now().isoformat()
        }
    }
    
    return resultado


def test_xml_generator():
    """Testa o gerador XML com diferentes tipos de documentos"""
    print("🧪 Teste do Gerador XML para Documentos Jurídicos")
    print("=" * 60)
    
    # Criar resultado OCR de exemplo
    resultado_ocr = criar_resultado_ocr_exemplo()
    
    # Inicializar gerador
    generator = XMLOutputGenerator()
    
    # Teste 1: Detecção automática de tipo
    print("\n1. 🔍 Teste de Detecção Automática de Tipo")
    print("-" * 40)
    
    texto_completo = generator._extrair_texto_completo(resultado_ocr)
    tipo_detectado = generator._detectar_tipo_documento(texto_completo)
    print(f"Tipo detectado: {tipo_detectado}")
    
    # Teste 2: Geração XML automática
    print("\n2. ⚡ Teste de Geração XML Automática")
    print("-" * 40)
    
    xml_content = gerar_xml_juridico(resultado_ocr, 'auto')
    print("XML gerado com sucesso!")
    print(f"Tamanho do XML: {len(xml_content)} caracteres")
    
    # Salvar XML de exemplo
    with open('/tmp/exemplo_relatorio_administrador.xml', 'w', encoding='utf-8') as f:
        f.write(xml_content)
    
    print("✅ XML salvo em: /tmp/exemplo_relatorio_administrador.xml")
    
    # Teste 3: Geração XML para cada tipo específico
    print("\n3. 📋 Teste de Templates Específicos")
    print("-" * 40)
    
    tipos_templates = [
        'manifestacao_processual',
        'relatorio_administrador', 
        'quadro_credores',
        'documento_generico'
    ]
    
    for tipo in tipos_templates:
        try:
            xml_content = generator.generate_xml(resultado_ocr, tipo)
            filename = f'/tmp/exemplo_{tipo}.xml'
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            print(f"✅ {tipo}: XML criado ({len(xml_content)} chars)")
            
        except Exception as e:
            print(f"❌ {tipo}: Erro - {str(e)}")
    
    # Teste 4: Validação de estrutura XML
    print("\n4. 🔍 Teste de Validação XML")
    print("-" * 40)
    
    try:
        import xml.etree.ElementTree as ET
        
        # Testar se o XML é bem formado
        root = ET.fromstring(xml_content)
        print("✅ XML bem formado")
        
        # Verificar elementos principais
        elementos_esperados = ['cabecalho', 'relatorio', 'metadados']
        for elem in elementos_esperados:
            if root.find(elem) is not None:
                print(f"✅ Elemento '{elem}' encontrado")
            else:
                print(f"⚠️ Elemento '{elem}' não encontrado")
                
    except Exception as e:
        print(f"❌ Erro na validação XML: {str(e)}")
    
    # Teste 5: Metadados e estatísticas
    print("\n5. 📊 Teste de Metadados")
    print("-" * 40)
    
    try:
        metadados = root.find('metadados')
        if metadados is not None:
            ocr_info = metadados.find('informacoesOCR')
            if ocr_info is not None:
                print(f"✅ Método OCR: {ocr_info.get('metodo')}")
                print(f"✅ Confiança: {ocr_info.get('confiancaMedia')}")
                print(f"✅ Tempo: {ocr_info.get('tempoProcessamento')}s")
            
            stats = metadados.find('estatisticas')
            if stats is not None:
                print(f"✅ Páginas: {stats.get('totalPaginas')}")
                print(f"✅ Caracteres: {stats.get('caracteresExtraidos')}")
                
    except Exception as e:
        print(f"❌ Erro ao verificar metadados: {str(e)}")
    
    print("\n🎉 Teste concluído!")
    print("=" * 60)


def test_extracoes_especificas():
    """Testa as extrações específicas de dados jurídicos"""
    print("\n🔬 Teste de Extrações Específicas")
    print("=" * 60)
    
    resultado_ocr = criar_resultado_ocr_exemplo()
    generator = XMLOutputGenerator()
    texto_completo = generator._extrair_texto_completo(resultado_ocr)
    
    # Teste de extração de eventos
    print("\n1. 📅 Extração de Eventos do Histórico")
    print("-" * 40)
    eventos = generator._extrair_eventos_historico(texto_completo)
    for evento in eventos:
        print(f"  📌 {evento['data']}: {evento['descricao']}")
    
    # Teste de extração de credores
    print("\n2. 💰 Extração de Quadro de Credores")
    print("-" * 40)
    credores = generator._extrair_quadro_credores(texto_completo)
    for credor in credores:
        print(f"  {credor['item']}. {credor['nome']} - {credor['valor']} ({credor['classificacao']})")
    
    # Teste de extração de pedidos
    print("\n3. 📋 Extração de Pedidos")
    print("-" * 40)
    pedidos = generator._extrair_pedidos(texto_completo)
    for i, pedido in enumerate(pedidos, 1):
        print(f"  {i}. {pedido}")
    
    # Teste de extração de irresignações
    print("\n4. ⚖️ Extração de Irresignações")
    print("-" * 40)
    irresignacoes = generator._extrair_irresignacoes(texto_completo)
    for irr in irresignacoes:
        print(f"  ID: {irr['id']}")
        if 'credorCorrigido' in irr:
            cc = irr['credorCorrigido']
            print(f"    Credor corrigido: {cc['nome']} - {cc['valor']} ({cc['classificacao']})")


if __name__ == "__main__":
    test_xml_generator()
    test_extracoes_especificas()