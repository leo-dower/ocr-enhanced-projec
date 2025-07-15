"""
XML Output Generator para documentos jurídicos
Gera saída estruturada em XML para manifestações processuais, relatórios e outros documentos jurídicos
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
import re
import datetime
from typing import Dict, List, Any, Optional
import json


class XMLOutputGenerator:
    """Gerador de saída XML para documentos jurídicos"""
    
    def __init__(self):
        self.templates = {
            'manifestacao_processual': self._template_manifestacao_processual,
            'relatorio_administrador': self._template_relatorio_administrador,
            'quadro_credores': self._template_quadro_credores,
            'documento_generico': self._template_documento_generico
        }
    
    def generate_xml(self, resultado_ocr: Dict[str, Any], template_type: str = 'documento_generico', 
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Gera XML estruturado baseado no resultado do OCR
        
        Args:
            resultado_ocr: Resultado do processamento OCR
            template_type: Tipo de template XML a ser usado
            metadata: Metadados adicionais para o documento
            
        Returns:
            String XML formatada
        """
        if template_type not in self.templates:
            template_type = 'documento_generico'
        
        # Processar texto do OCR
        texto_completo = self._extrair_texto_completo(resultado_ocr)
        
        # Detectar automaticamente tipo de documento se não especificado
        if template_type == 'documento_generico':
            template_type = self._detectar_tipo_documento(texto_completo)
        
        # Aplicar template específico
        root = self.templates[template_type](resultado_ocr, texto_completo, metadata or {})
        
        # Converter para string XML formatada
        return self._prettify_xml(root)
    
    def _extrair_texto_completo(self, resultado_ocr: Dict[str, Any]) -> str:
        """Extrai texto completo do resultado OCR"""
        texto_completo = ""
        pages = resultado_ocr.get("pages", [])
        
        for page in pages:
            texto_pagina = page.get("text", "")
            if texto_pagina.strip():
                texto_completo += texto_pagina + "\n"
        
        return texto_completo.strip()
    
    def _detectar_tipo_documento(self, texto: str) -> str:
        """Detecta automaticamente o tipo de documento baseado no conteúdo"""
        texto_lower = texto.lower()
        
        # Patterns para manifestação processual
        manifestacao_patterns = [
            r'manifestação',
            r'excelentíssimo',
            r'meritíssimo',
            r'processo.*n[uú]mero',
            r'requerente',
            r'requerido',
            r'vara.*cível',
            r'tribunal.*justiça'
        ]
        
        # Patterns para relatório de administrador
        relatorio_patterns = [
            r'relatório.*administrador',
            r'recuperação.*judicial',
            r'administrador.*judicial',
            r'quadro.*credores',
            r'passivo.*ativo',
            r'oab.*\d+',
            r'irresignação'
        ]
        
        # Patterns para quadro de credores
        quadro_patterns = [
            r'quadro.*geral.*credores',
            r'classificação.*credor',
            r'garantia.*real',
            r'quirografário',
            r'trabalhista',
            r'valor.*crédito'
        ]
        
        # Contar matches
        manifestacao_score = sum(1 for pattern in manifestacao_patterns if re.search(pattern, texto_lower))
        relatorio_score = sum(1 for pattern in relatorio_patterns if re.search(pattern, texto_lower))
        quadro_score = sum(1 for pattern in quadro_patterns if re.search(pattern, texto_lower))
        
        # Retornar tipo com maior score
        scores = {
            'manifestacao_processual': manifestacao_score,
            'relatorio_administrador': relatorio_score,
            'quadro_credores': quadro_score
        }
        
        max_score = max(scores.values())
        if max_score >= 2:  # Threshold mínimo
            return max(scores, key=scores.get)
        
        return 'documento_generico'
    
    def _template_manifestacao_processual(self, resultado_ocr: Dict, texto: str, metadata: Dict) -> ET.Element:
        """Template para manifestações processuais"""
        root = ET.Element('manifestacao')
        
        # Cabeçalho
        cabecalho = ET.SubElement(root, 'cabecalho')
        
        # Extrair número do processo
        processo_match = re.search(r'processo.*?n[uú]mero.*?(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})', texto, re.IGNORECASE)
        processo_numero = processo_match.group(1) if processo_match else "N/A"
        
        # Extrair vara
        vara_match = re.search(r'(\d+[ªº]?\s*vara.*?)', texto, re.IGNORECASE)
        vara = vara_match.group(1) if vara_match else "N/A"
        
        # Extrair comarca
        comarca_match = re.search(r'comarca.*?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', texto, re.IGNORECASE)
        comarca = comarca_match.group(1) if comarca_match else "N/A"
        
        processo_elem = ET.SubElement(cabecalho, 'processo')
        processo_elem.set('numero', processo_numero)
        processo_elem.set('vara', vara)
        processo_elem.set('comarca', comarca)
        
        # Data de processamento
        data_elem = ET.SubElement(cabecalho, 'data')
        data_elem.text = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # Conteúdo principal
        conteudo = ET.SubElement(root, 'conteudo')
        
        # Dividir texto em seções
        secoes = self._dividir_texto_secoes(texto)
        
        for titulo, conteudo_secao in secoes.items():
            secao_elem = ET.SubElement(conteudo, 'secao')
            secao_elem.set('titulo', titulo)
            secao_elem.text = conteudo_secao
        
        # Metadados do OCR
        self._adicionar_metadados_ocr(root, resultado_ocr, metadata)
        
        return root
    
    def _template_relatorio_administrador(self, resultado_ocr: Dict, texto: str, metadata: Dict) -> ET.Element:
        """Template para relatórios de administrador judicial"""
        root = ET.Element('manifestacao')
        
        # Cabeçalho
        cabecalho = ET.SubElement(root, 'cabecalho')
        
        # Extrair dados do processo
        processo_match = re.search(r'processo.*?n[uú]mero.*?(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})', texto, re.IGNORECASE)
        processo_numero = processo_match.group(1) if processo_match else "N/A"
        
        vara_match = re.search(r'(\d+[ªº]?\s*vara.*?)', texto, re.IGNORECASE)
        vara = vara_match.group(1) if vara_match else "N/A"
        
        comarca_match = re.search(r'comarca.*?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', texto, re.IGNORECASE)
        comarca = comarca_match.group(1) if comarca_match else "N/A"
        
        processo_elem = ET.SubElement(cabecalho, 'processo')
        processo_elem.set('numero', processo_numero)
        processo_elem.set('vara', vara)
        processo_elem.set('comarca', comarca)
        
        # Administrador
        admin_match = re.search(r'administrador.*?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', texto, re.IGNORECASE)
        admin_nome = admin_match.group(1) if admin_match else "N/A"
        
        oab_match = re.search(r'oab.*?(\w+/\w+\s*\d+\.?\d*)', texto, re.IGNORECASE)
        oab_numero = oab_match.group(1) if oab_match else "N/A"
        
        admin_elem = ET.SubElement(cabecalho, 'administrador')
        admin_elem.set('nome', admin_nome)
        admin_elem.set('oab', oab_numero)
        
        # Data
        data_elem = ET.SubElement(cabecalho, 'data')
        data_elem.text = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # Relatório
        relatorio = ET.SubElement(root, 'relatorio')
        
        # Histórico
        historico = ET.SubElement(relatorio, 'historico')
        eventos = self._extrair_eventos_historico(texto)
        for evento in eventos:
            evento_elem = ET.SubElement(historico, 'evento')
            evento_elem.set('data', evento.get('data', 'N/A'))
            evento_elem.set('descricao', evento.get('descricao', ''))
        
        # Situação atual
        situacao = ET.SubElement(relatorio, 'situacaoAtual')
        
        # Extrair valores de passivo e ativo
        passivo_match = re.search(r'passivo.*?(\d+\.?\d*\.?\d*,\d{2})', texto, re.IGNORECASE)
        if passivo_match:
            passivo_elem = ET.SubElement(situacao, 'passivo')
            passivo_elem.set('valor', passivo_match.group(1))
        
        ativo_match = re.search(r'ativo.*?(não\s+arrecadado|arrecadado)', texto, re.IGNORECASE)
        if ativo_match:
            ativo_elem = ET.SubElement(situacao, 'ativo')
            ativo_elem.set('status', ativo_match.group(1))
        
        # Descrição da situação
        descricao_elem = ET.SubElement(situacao, 'descricao')
        descricao_elem.text = self._extrair_descricao_situacao(texto)
        
        # Irresignações
        irresignacoes = ET.SubElement(relatorio, 'irresignacoes')
        irresignacoes_lista = self._extrair_irresignacoes(texto)
        for irr in irresignacoes_lista:
            irr_elem = ET.SubElement(irresignacoes, 'irresignacao')
            irr_elem.set('id', irr.get('id', ''))
            
            if 'credorCorrigido' in irr:
                cc = irr['credorCorrigido']
                cc_elem = ET.SubElement(irr_elem, 'credorCorrigido')
                cc_elem.set('nome', cc.get('nome', ''))
                cc_elem.set('valor', cc.get('valor', ''))
                cc_elem.set('classificacao', cc.get('classificacao', ''))
            
            if 'novoCredor' in irr:
                nc = irr['novoCredor']
                nc_elem = ET.SubElement(irr_elem, 'novoCredor')
                nc_elem.set('nome', nc.get('nome', ''))
                nc_elem.set('valor', nc.get('valor', ''))
                nc_elem.set('classificacao', nc.get('classificacao', ''))
        
        # Pedidos
        pedidos = ET.SubElement(relatorio, 'pedidos')
        pedidos_lista = self._extrair_pedidos(texto)
        for pedido in pedidos_lista:
            pedido_elem = ET.SubElement(pedidos, 'pedido')
            pedido_elem.text = pedido
        
        # Anexos (se houver quadro de credores)
        if 'quadro' in texto.lower() and 'credores' in texto.lower():
            anexos = ET.SubElement(root, 'anexos')
            quadro = ET.SubElement(anexos, 'quadroGeralDeCredores')
            
            credores = self._extrair_quadro_credores(texto)
            for credor in credores:
                credor_elem = ET.SubElement(quadro, 'credor')
                
                item_elem = ET.SubElement(credor_elem, 'item')
                item_elem.text = credor.get('item', '')
                
                nome_elem = ET.SubElement(credor_elem, 'nome')
                nome_elem.text = credor.get('nome', '')
                
                valor_elem = ET.SubElement(credor_elem, 'valor')
                valor_elem.text = credor.get('valor', '')
                
                class_elem = ET.SubElement(credor_elem, 'classificacao')
                class_elem.text = credor.get('classificacao', '')
        
        # Metadados do OCR
        self._adicionar_metadados_ocr(root, resultado_ocr, metadata)
        
        return root
    
    def _template_quadro_credores(self, resultado_ocr: Dict, texto: str, metadata: Dict) -> ET.Element:
        """Template específico para quadro de credores"""
        root = ET.Element('quadroGeralDeCredores')
        
        # Metadados
        info = ET.SubElement(root, 'informacoes')
        info.set('dataProcessamento', datetime.datetime.now().strftime('%Y-%m-%d'))
        info.set('totalPaginas', str(len(resultado_ocr.get('pages', []))))
        
        # Extrair credores
        credores = self._extrair_quadro_credores(texto)
        
        for credor in credores:
            credor_elem = ET.SubElement(root, 'credor')
            
            item_elem = ET.SubElement(credor_elem, 'item')
            item_elem.text = credor.get('item', '')
            
            nome_elem = ET.SubElement(credor_elem, 'nome')
            nome_elem.text = credor.get('nome', '')
            
            valor_elem = ET.SubElement(credor_elem, 'valor')
            valor_elem.text = credor.get('valor', '')
            
            class_elem = ET.SubElement(credor_elem, 'classificacao')
            class_elem.text = credor.get('classificacao', '')
        
        # Metadados do OCR
        self._adicionar_metadados_ocr(root, resultado_ocr, metadata)
        
        return root
    
    def _template_documento_generico(self, resultado_ocr: Dict, texto: str, metadata: Dict) -> ET.Element:
        """Template genérico para documentos não específicos"""
        root = ET.Element('documento')
        
        # Informações básicas
        info = ET.SubElement(root, 'informacoes')
        info.set('dataProcessamento', datetime.datetime.now().strftime('%Y-%m-%d'))
        info.set('totalPaginas', str(len(resultado_ocr.get('pages', []))))
        info.set('tipoDocumento', metadata.get('tipo', 'generico'))
        
        # Conteúdo completo
        conteudo = ET.SubElement(root, 'conteudo')
        conteudo.text = texto
        
        # Páginas individuais
        paginas = ET.SubElement(root, 'paginas')
        for i, page in enumerate(resultado_ocr.get('pages', []), 1):
            pagina_elem = ET.SubElement(paginas, 'pagina')
            pagina_elem.set('numero', str(i))
            pagina_elem.set('confianca', str(page.get('confidence', 0)))
            pagina_elem.text = page.get('text', '')
        
        # Metadados do OCR
        self._adicionar_metadados_ocr(root, resultado_ocr, metadata)
        
        return root
    
    def _dividir_texto_secoes(self, texto: str) -> Dict[str, str]:
        """Divide o texto em seções baseado em padrões comuns"""
        secoes = {}
        
        # Padrões para identificar seções
        patterns = {
            'dos_fatos': r'(dos\s+fatos|fatos\s+e\s+fundamentos)',
            'do_direito': r'(do\s+direito|fundamentos\s+jurídicos)',
            'dos_pedidos': r'(dos\s+pedidos|pedidos)',
            'conclusao': r'(conclus[aã]o|por\s+fim)',
            'introducao': r'(introdu[çc][aã]o|preliminar)'
        }
        
        # Dividir texto em parágrafos
        paragrafos = texto.split('\n\n')
        secao_atual = 'conteudo_principal'
        
        for paragrafo in paragrafos:
            # Verificar se o parágrafo marca início de nova seção
            for nome_secao, pattern in patterns.items():
                if re.search(pattern, paragrafo.lower()):
                    secao_atual = nome_secao
                    break
            
            if secao_atual not in secoes:
                secoes[secao_atual] = ""
            
            secoes[secao_atual] += paragrafo + "\n\n"
        
        return secoes
    
    def _extrair_eventos_historico(self, texto: str) -> List[Dict[str, str]]:
        """Extrai eventos do histórico do processo"""
        eventos = []
        
        # Padrões para datas
        date_patterns = [
            r'(\d{2}/\d{2}/\d{4})',
            r'(\d{2}-\d{2}-\d{4})',
            r'(\d{4}-\d{2}-\d{2})'
        ]
        
        linhas = texto.split('\n')
        for linha in linhas:
            for pattern in date_patterns:
                match = re.search(pattern, linha)
                if match:
                    data = match.group(1)
                    # Remover a data da linha para obter a descrição
                    descricao = re.sub(pattern, '', linha).strip()
                    if descricao:
                        eventos.append({
                            'data': data,
                            'descricao': descricao
                        })
                    break
        
        return eventos
    
    def _extrair_descricao_situacao(self, texto: str) -> str:
        """Extrai descrição da situação atual"""
        # Procurar por padrões que indicam situação atual
        patterns = [
            r'situação.*?atual[:\s]+(.*?)(?=\n\n|\n[A-Z])',
            r'empresas.*?em.*?(.*?)(?=\n\n|\n[A-Z])',
            r'estado.*?atual[:\s]+(.*?)(?=\n\n|\n[A-Z])'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, texto, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return "Situação não especificada"
    
    def _extrair_irresignacoes(self, texto: str) -> List[Dict[str, Any]]:
        """Extrai informações sobre irresignações"""
        irresignacoes = []
        
        # Padrão para identificar irresignações
        pattern = r'irresignação.*?(\d+).*?credor.*?corrigido.*?([A-Z][^,]*?).*?valor.*?(\d+\.?\d*,\d{2}).*?classificação.*?([A-Z]+)'
        
        matches = re.finditer(pattern, texto, re.IGNORECASE | re.DOTALL)
        for match in matches:
            irresignacao = {
                'id': match.group(1),
                'credorCorrigido': {
                    'nome': match.group(2).strip(),
                    'valor': match.group(3),
                    'classificacao': match.group(4)
                }
            }
            irresignacoes.append(irresignacao)
        
        return irresignacoes
    
    def _extrair_pedidos(self, texto: str) -> List[str]:
        """Extrai lista de pedidos"""
        pedidos = []
        
        # Procurar seção de pedidos
        pedidos_match = re.search(r'pedidos?[:\s]+(.*?)(?=\n\n[A-Z]|\n[A-Z][a-z]*:|\Z)', texto, re.IGNORECASE | re.DOTALL)
        if pedidos_match:
            pedidos_text = pedidos_match.group(1)
            
            # Dividir em itens (procurar por numeração ou bullet points)
            items = re.split(r'(?:^|\n)\s*(?:\d+\.?|\-|\*)\s*', pedidos_text)
            
            for item in items:
                item = item.strip()
                if item and len(item) > 10:  # Filtrar itens muito pequenos
                    pedidos.append(item)
        
        return pedidos
    
    def _extrair_quadro_credores(self, texto: str) -> List[Dict[str, str]]:
        """Extrai informações do quadro de credores"""
        credores = []
        
        # Padrão para linha do quadro de credores
        pattern = r'(\d+)\s+([A-Z][^0-9]*?)\s+(\d+\.?\d*\.?\d*,\d{2})\s+(GARANTIA\s+REAL|QUIROGRAFÁRIO|TRABALHISTA|TRIBUTÁRIO)'
        
        matches = re.finditer(pattern, texto, re.IGNORECASE)
        for match in matches:
            credor = {
                'item': match.group(1),
                'nome': match.group(2).strip(),
                'valor': match.group(3),
                'classificacao': match.group(4)
            }
            credores.append(credor)
        
        return credores
    
    def _adicionar_metadados_ocr(self, root: ET.Element, resultado_ocr: Dict, metadata: Dict):
        """Adiciona metadados do OCR ao XML"""
        meta = ET.SubElement(root, 'metadados')
        meta.set('versao', '1.0')
        
        # Informações do OCR
        ocr_info = ET.SubElement(meta, 'informacoesOCR')
        ocr_info.set('metodo', resultado_ocr.get('metadata', {}).get('method', 'unknown'))
        ocr_info.set('confiancaMedia', str(resultado_ocr.get('metadata', {}).get('average_confidence', 0)))
        ocr_info.set('tempoProcessamento', str(resultado_ocr.get('metadata', {}).get('processing_time', 0)))
        
        # Estatísticas
        stats = ET.SubElement(meta, 'estatisticas')
        stats.set('totalPaginas', str(len(resultado_ocr.get('pages', []))))
        stats.set('caracteresExtraidos', str(sum(len(p.get('text', '')) for p in resultado_ocr.get('pages', []))))
        
        # Metadados adicionais
        if metadata:
            extras = ET.SubElement(meta, 'metadados_extras')
            for key, value in metadata.items():
                extras.set(key, str(value))
    
    def _prettify_xml(self, elem: ET.Element) -> str:
        """Formata XML de forma legível"""
        rough_string = ET.tostring(elem, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")


def gerar_xml_juridico(resultado_ocr: Dict[str, Any], tipo_documento: str = 'auto', 
                      metadata: Optional[Dict[str, Any]] = None) -> str:
    """
    Função auxiliar para gerar XML jurídico
    
    Args:
        resultado_ocr: Resultado do processamento OCR
        tipo_documento: Tipo de documento ('auto', 'manifestacao_processual', 'relatorio_administrador', etc.)
        metadata: Metadados adicionais
    
    Returns:
        String XML formatada
    """
    generator = XMLOutputGenerator()
    
    if tipo_documento == 'auto':
        tipo_documento = 'documento_generico'
    
    return generator.generate_xml(resultado_ocr, tipo_documento, metadata)