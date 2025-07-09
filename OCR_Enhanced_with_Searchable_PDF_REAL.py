import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import os
import requests
import json
import socket
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import threading
import PyPDF2
import math
from pathlib import Path
import random
import datetime
import platform
import asyncio

# Importar sistema MCP
try:
    from src.mcp import MCPWorkflowManager, WorkflowResult, SearchManager
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("⚠️ Sistema MCP não disponível. Funcionalidade de workflow limitada.")

# Local OCR imports
try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

# PDF manipulation imports for searchable PDF generation
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.colors import Color
    import fitz  # PyMuPDF for advanced PDF manipulation
    PDF_GENERATION_AVAILABLE = True
except ImportError:
    PDF_GENERATION_AVAILABLE = False

class OCRBatchAppComplete:
    def __init__(self, root):
        self.root = root
        self.root.title("Enhanced OCR - Completo com PDF Pesquisável")
        self.root.geometry("1600x1000")
        self.root.resizable(True, True)

        # Configurações
        # Default folders - can be customized by end users
        self.pasta_padrao = os.path.expanduser("F:\\OneDrive\\Advocacia\\ano_2025")
        self.pasta_destino = os.path.expanduser("F:\\OneDrive\\Advocacia\\ano_2025")
        self.max_paginas_por_lote = 200  # Máximo de páginas por processamento
        self.max_paginas_divisao = 50    # Dividir arquivos maiores que isso
        self.arquivos_selecionados = []
        self.processamento_ativo = False
        self.max_tentativas = 3
        self.tempo_espera_base = 60
        
        # Configurações de timeout melhoradas
        self.timeout_upload = 120        # 2 minutos para upload
        self.timeout_ocr = 300          # 5 minutos para OCR
        self.timeout_por_pagina = 10    # 10 segundos por página
        
        # Sistema Multi-Engine OCR
        self.multi_engine_enabled = True
        self.engine_preferences = {
            'preferred_engines': ['azure_cloud', 'google_cloud', 'mistral_cloud'],
            'fallback_engines': ['tesseract_local'],
            'quality_threshold': 0.8,
            'enable_parallel_processing': False,
            'enable_quality_comparison': True
        }
        
        # Sistema de Processamento Paralelo
        self.parallel_processing_enabled = True
        self.parallel_processor = None
        self.max_parallel_workers = 3  # Número de arquivos processados simultaneamente
        self.parallel_stats = {
            'total_files': 0,
            'completed_files': 0,
            'successful_files': 0,
            'failed_files': 0,
            'cache_hits': 0,
            'avg_processing_time': 0.0,
            'throughput': 0.0
        }

        # Local processing settings
        self.modo_local_primeiro = True
        self.modo_privacidade = False
        self.qualidade_minima_local = 0.7
        self.usar_apenas_local = False

        # Searchable PDF settings
        self.gerar_pdf_pesquisavel = True
        self.manter_original = True
        self.qualidade_texto_pdf = 0.5

        # Estatísticas
        self.stats_local = 0
        self.stats_cloud = 0
        self.stats_failed = 0
        self.pdfs_gerados = 0
        self.tamanho_total_mb = 0

        # Sistema MCP Workflow
        self.mcp_manager = None
        self.workflow_enabled = False
        self.search_manager = None
        if MCP_AVAILABLE:
            try:
                self.mcp_manager = MCPWorkflowManager()
                self.workflow_enabled = self.mcp_manager.workflow_enabled
                self.search_manager = SearchManager()
            except Exception as e:
                print(f"⚠️ Erro ao inicializar MCP: {e}")
        
        # Sistema Multi-Engine OCR
        self.multi_engine_system = None
        self.available_engines = []
        self.engine_stats = {}
        self.init_multi_engine_system()

        # Inicializar processamento paralelo
        self.init_parallel_processing()
        
        # Criar interface
        self.criar_interface()
    
    def init_multi_engine_system(self):
        """Inicializar sistema multi-engine OCR com cache inteligente."""
        try:
            from src.ocr.multi_engine import create_multi_engine_ocr, EnginePreferences
            from src.ocr.base import OCROptions
            
            # Criar preferências
            preferences = EnginePreferences(
                preferred_engines=self.engine_preferences['preferred_engines'],
                fallback_engines=self.engine_preferences['fallback_engines'],
                quality_threshold=self.engine_preferences['quality_threshold'],
                enable_parallel_processing=self.engine_preferences['enable_parallel_processing'],
                enable_quality_comparison=self.engine_preferences['enable_quality_comparison']
            )
            
            # Criar sistema multi-engine com cache inteligente
            self.multi_engine_system = create_multi_engine_ocr(
                preferences=preferences,
                enable_cache=True,  # Ativar cache inteligente
                cache_dir=None      # Usar diretório padrão ~/.ocr_cache
            )
            
            # Registrar engines disponíveis
            self.register_available_engines()
            
            self.adicionar_log("🚀 Sistema Multi-Engine OCR inicializado com cache inteligente")
            self.adicionar_log(f"🔧 Engines disponíveis: {len(self.available_engines)}")
            
            # Mostrar estatísticas do cache
            cache_stats = self.multi_engine_system.get_cache_statistics()
            if cache_stats.get('cache_enabled'):
                total_entries = cache_stats.get('total_entries', 0)
                cache_size = cache_stats.get('cache_size_mb', 0)
                hit_rate = cache_stats.get('hit_rate', 0) * 100
                self.adicionar_log(f"💾 Cache: {total_entries} entradas, {cache_size:.1f}MB, {hit_rate:.1f}% acertos")
            
        except Exception as e:
            self.adicionar_log(f"⚠️ Erro ao inicializar Multi-Engine: {e}")
            self.multi_engine_system = None

    def verificar_dependencias_pdf(self):
        """Verificar se dependências para PDF pesquisável estão disponíveis"""
        if not PDF_GENERATION_AVAILABLE:
            return False, "Bibliotecas não instaladas (reportlab, PyMuPDF)"
        
        try:
            import reportlab
            import fitz
            return True, f"reportlab {reportlab.Version} e PyMuPDF disponíveis"
        except Exception as e:
            return False, f"Erro ao verificar dependências PDF: {str(e)}"

    def verificar_tesseract(self):
        """Verificar se Tesseract está instalado e configurado"""
        if not TESSERACT_AVAILABLE:
            return False, "Bibliotecas não instaladas (pytesseract, pdf2image, pillow)"
        
        try:
            tesseract_path = pytesseract.pytesseract.tesseract_cmd
            if not os.path.exists(tesseract_path):
                common_paths = [
                    '/usr/bin/tesseract',
                    '/usr/local/bin/tesseract',
                    'C:\\Program Files\\Tesseract-OCR\\tesseract.exe',
                    'C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe'
                ]
                
                for path in common_paths:
                    if os.path.exists(path):
                        pytesseract.pytesseract.tesseract_cmd = path
                        tesseract_path = path
                        break
                else:
                    return False, "Tesseract não encontrado"
            
            version = pytesseract.get_tesseract_version()
            return True, f"Tesseract {version} encontrado em {tesseract_path}"
            
        except Exception as e:
            return False, f"Erro ao verificar Tesseract: {str(e)}"

    def criar_interface(self):
        # Frame principal com layout de quatro colunas
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Configurar colunas
        main_frame.grid_columnconfigure(0, weight=2)  # Controles principais
        main_frame.grid_columnconfigure(1, weight=1)  # Configurações locais
        main_frame.grid_columnconfigure(2, weight=1)  # Configurações PDF
        main_frame.grid_columnconfigure(3, weight=2)  # Log
        main_frame.grid_rowconfigure(0, weight=1)

        # Frames
        left_frame = tk.Frame(main_frame, relief="raised", bd=1)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_frame.grid_columnconfigure(1, weight=1)

        center_frame = tk.Frame(main_frame, relief="raised", bd=1)
        center_frame.grid(row=0, column=1, sticky="nsew", padx=5)
        center_frame.grid_columnconfigure(0, weight=1)

        pdf_frame = tk.Frame(main_frame, relief="raised", bd=1)
        pdf_frame.grid(row=0, column=2, sticky="nsew", padx=5)
        pdf_frame.grid_columnconfigure(0, weight=1)

        right_frame = tk.Frame(main_frame, relief="raised", bd=1)
        right_frame.grid(row=0, column=3, sticky="nsew", padx=(5, 0))
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)

        # Criar seções
        self.criar_controles_principais(left_frame)
        self.criar_configuracoes_locais(center_frame)
        self.criar_configuracoes_pdf(pdf_frame)
        self.criar_area_log(right_frame)

        # Verificar dependências na inicialização
        self.verificar_dependencias_inicial()
        
        # Log de inicialização com status dos formatos
        self.adicionar_log("🚀 Enhanced OCR com PDF Pesquisável - VERSÃO CORRIGIDA")
        self.adicionar_log(f"📋 JSON: {'✅ Habilitado' if self.gerar_json_var.get() else '❌ Desabilitado'}")
        self.adicionar_log(f"📝 Markdown: {'✅ Habilitado' if self.gerar_md_var.get() else '❌ Desabilitado'}")
        self.adicionar_log(f"🔍 PDF Pesquisável: {'✅ Habilitado' if self.gerar_pdf_var.get() else '❌ Desabilitado'}")
        self.adicionar_log(f"🔧 PyMuPDF: {'✅ Disponível' if PDF_GENERATION_AVAILABLE else '❌ Não disponível'}")

    def criar_configuracoes_pdf(self, parent):
        """Criar área de configurações para PDF pesquisável"""
        # Título
        titulo_pdf = tk.Label(parent, text="PDF Pesquisável", 
                             font=("Arial", 12, "bold"), fg="darkblue")
        titulo_pdf.grid(row=0, column=0, pady=10, padx=5)

        # Status das dependências
        deps_frame = tk.LabelFrame(parent, text="Status das Dependências", font=("Arial", 10, "bold"))
        deps_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        deps_frame.grid_columnconfigure(0, weight=1)

        self.pdf_deps_label = tk.Label(deps_frame, text="Verificando...", 
                                      fg="orange", font=("Arial", 9))
        self.pdf_deps_label.grid(row=0, column=0, pady=5, padx=5)

        self.verificar_deps_button = tk.Button(deps_frame, text="Verificar Novamente", 
                                              command=self.verificar_dependencias_inicial,
                                              bg="lightblue", font=("Arial", 8))
        self.verificar_deps_button.grid(row=1, column=0, pady=5)

        # Configurações de divisão automática
        divisao_frame = tk.LabelFrame(parent, text="Divisão Automática", font=("Arial", 10, "bold"))
        divisao_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        divisao_frame.grid_columnconfigure(1, weight=1)
        
        tk.Label(divisao_frame, text="Dividir PDFs com mais de:", font=("Arial", 9)).grid(
            row=0, column=0, sticky="e", padx=5, pady=3)
        
        self.max_paginas_var = tk.IntVar(value=self.max_paginas_divisao)
        divisao_spinbox = tk.Spinbox(divisao_frame, from_=10, to=200, 
                                   textvariable=self.max_paginas_var,
                                   width=10, font=("Arial", 9),
                                   command=self.atualizar_limite_divisao)
        divisao_spinbox.grid(row=0, column=1, sticky="w", padx=5, pady=3)
        
        tk.Label(divisao_frame, text="páginas", font=("Arial", 9)).grid(
            row=0, column=2, sticky="w", padx=5, pady=3)
        
        # Info sobre divisão
        info_label = tk.Label(divisao_frame, 
                            text="💡 Arquivos grandes são divididos automaticamente\npara evitar timeouts", 
                            font=("Arial", 8), fg="darkblue", justify=tk.LEFT)
        info_label.grid(row=1, column=0, columnspan=3, sticky="w", padx=5, pady=2)

        # Configurações de saída
        output_frame = tk.LabelFrame(parent, text="Configurações de Saída", font=("Arial", 10, "bold"))
        output_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        output_frame.grid_columnconfigure(0, weight=1)

        # Checkboxes para tipos de saída
        self.gerar_json_var = tk.BooleanVar(value=True)
        tk.Checkbutton(output_frame, text="Gerar JSON", 
                      variable=self.gerar_json_var, font=("Arial", 9)).grid(
            row=0, column=0, sticky="w", padx=5, pady=2)

        self.gerar_md_var = tk.BooleanVar(value=True)
        tk.Checkbutton(output_frame, text="Gerar Markdown", 
                      variable=self.gerar_md_var, font=("Arial", 9)).grid(
            row=1, column=0, sticky="w", padx=5, pady=2)

        self.gerar_pdf_var = tk.BooleanVar(value=True)
        tk.Checkbutton(output_frame, text="Gerar PDF pesquisável", 
                      variable=self.gerar_pdf_var, font=("Arial", 9),
                      command=self.atualizar_opcoes_pdf).grid(
            row=2, column=0, sticky="w", padx=5, pady=2)

        # Configurações específicas do PDF
        pdf_config_frame = tk.LabelFrame(parent, text="Configurações do PDF", font=("Arial", 10, "bold"))
        pdf_config_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=5)
        pdf_config_frame.grid_columnconfigure(1, weight=1)

        self.manter_original_var = tk.BooleanVar(value=True)
        tk.Checkbutton(pdf_config_frame, text="Manter PDF original", 
                      variable=self.manter_original_var, font=("Arial", 9)).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=5, pady=2)

        # Qualidade do texto no PDF
        tk.Label(pdf_config_frame, text="Confiança mín.:", font=("Arial", 9)).grid(
            row=1, column=0, sticky="e", padx=5, pady=3)
        
        self.qualidade_pdf_scale = tk.Scale(pdf_config_frame, from_=0.1, to=1.0, 
                                           resolution=0.1, orient=tk.HORIZONTAL,
                                           font=("Arial", 8))
        self.qualidade_pdf_scale.set(self.qualidade_texto_pdf)
        self.qualidade_pdf_scale.grid(row=1, column=1, sticky="ew", padx=5, pady=3)

        # Método de geração
        method_frame = tk.LabelFrame(parent, text="Método de Geração", font=("Arial", 10, "bold"))
        method_frame.grid(row=4, column=0, sticky="ew", padx=5, pady=5)
        method_frame.grid_columnconfigure(0, weight=1)

        self.metodo_pdf_var = tk.StringVar(value="overlay")
        metodos = [
            ("Sobreposição invisível", "overlay"),
            ("Nova camada de texto", "layer"),
        ]
        
        for i, (texto, valor) in enumerate(metodos):
            tk.Radiobutton(method_frame, text=texto, variable=self.metodo_pdf_var, 
                          value=valor, font=("Arial", 8)).grid(
                row=i, column=0, sticky="w", padx=5, pady=1)

        # Estatísticas de PDF
        stats_pdf_frame = tk.LabelFrame(parent, text="Estatísticas PDF", font=("Arial", 10, "bold"))
        stats_pdf_frame.grid(row=5, column=0, sticky="ew", padx=5, pady=5)
        stats_pdf_frame.grid_columnconfigure(0, weight=1)

        self.stats_pdf_gerados = tk.Label(stats_pdf_frame, text="PDFs criados: 0", 
                                         fg="blue", font=("Arial", 9))
        self.stats_pdf_gerados.grid(row=0, column=0, sticky="w", padx=5, pady=2)

        self.stats_tamanho_total = tk.Label(stats_pdf_frame, text="Tamanho total: 0 MB", 
                                           fg="purple", font=("Arial", 9))
        self.stats_tamanho_total.grid(row=1, column=0, sticky="w", padx=5, pady=2)

    def atualizar_opcoes_pdf(self):
        """Atualizar interface baseada na seleção de PDF"""
        if self.gerar_pdf_var.get():
            self.adicionar_log("📄 Geração de PDF pesquisável ativada")
        else:
            self.adicionar_log("📄 Geração de PDF pesquisável desativada")
    
    def atualizar_limite_divisao(self):
        """Atualizar limite de divisão automática"""
        try:
            novo_limite = self.max_paginas_var.get()
            self.max_paginas_divisao = novo_limite
            self.adicionar_log(f"📂 Limite de divisão atualizado: {novo_limite} páginas")
        except:
            pass  # Ignorar se não conseguir obter o valor

    def verificar_dependencias_inicial(self):
        """Verificar todas as dependências na inicialização"""
        def verificar():
            # Tesseract
            tesseract_ok, tesseract_msg = self.verificar_tesseract()
            
            # PDF dependencies
            pdf_ok, pdf_msg = self.verificar_dependencias_pdf()
            
            if tesseract_ok:
                self.adicionar_log(f"✅ {tesseract_msg}")
            else:
                self.adicionar_log(f"❌ {tesseract_msg}")
            
            if pdf_ok:
                self.pdf_deps_label.config(text="✅ ReportLab e PyMuPDF OK", fg="green")
                self.adicionar_log(f"✅ {pdf_msg}")
            else:
                self.pdf_deps_label.config(text="❌ Dependências PDF faltando", fg="red")
                self.adicionar_log(f"❌ {pdf_msg}")
                self.adicionar_log("💡 Para instalar: pip install reportlab PyMuPDF")
        
        thread = threading.Thread(target=verificar)
        thread.daemon = True
        thread.start()

    def criar_pdf_pesquisavel(self, ocr_result, caminho_pdf_original, nome_base):
        """Criar PDF pesquisável com camada de texto invisível"""
        if not PDF_GENERATION_AVAILABLE:
            self.adicionar_log("❌ Dependências para PDF pesquisável não disponíveis")
            return None

        if not self.gerar_pdf_var.get():
            return None

        try:
            self.adicionar_log(f"📄 Criando PDF pesquisável: {nome_base}")
            
            metodo = self.metodo_pdf_var.get()
            confianca_minima = self.qualidade_pdf_scale.get()
            
            if metodo == "overlay":
                return self.criar_pdf_overlay(ocr_result, caminho_pdf_original, nome_base, confianca_minima)
            else:  # layer
                return self.criar_pdf_camada(ocr_result, caminho_pdf_original, nome_base, confianca_minima)
                
        except Exception as e:
            self.adicionar_log(f"❌ Erro ao criar PDF pesquisável: {str(e)}")
            return None

    def criar_pdf_overlay(self, ocr_result, caminho_pdf_original, nome_base, confianca_minima):
        """Criar PDF com texto invisível sobreposto (método mais compatível)"""
        try:
            self.adicionar_log(f"🔧 Iniciando criação de PDF pesquisável para {nome_base}")
            
            # Verificar se o arquivo original existe
            if not os.path.exists(caminho_pdf_original):
                self.adicionar_log(f"❌ Arquivo original não encontrado: {caminho_pdf_original}")
                return None
            
            # Abrir PDF original com PyMuPDF
            self.adicionar_log(f"📂 Abrindo PDF original: {os.path.basename(caminho_pdf_original)}")
            doc_original = fitz.open(caminho_pdf_original)
            
            # Criar novo documento
            doc_novo = fitz.open()
            
            pages_data = ocr_result.get("pages", [])
            self.adicionar_log(f"📄 Processando {len(pages_data)} páginas de OCR")
            
            texto_adicionado_total = 0
            
            for page_num, page_original in enumerate(doc_original):
                # Copiar página original
                nova_pagina = doc_novo.new_page(width=page_original.rect.width, 
                                               height=page_original.rect.height)
                
                # Inserir conteúdo original (imagem)
                nova_pagina.show_pdf_page(nova_pagina.rect, doc_original, page_num)
                
                # Adicionar texto invisível se disponível
                if page_num < len(pages_data):
                    page_data = pages_data[page_num]
                    texto = page_data.get("text", "")
                    confidence = page_data.get("confidence", 0)
                    
                    if texto.strip() and confidence >= confianca_minima:
                        # Inserir texto invisível com método aprimorado
                        sucesso = self.adicionar_texto_invisivel_fitz(nova_pagina, texto)
                        if sucesso:
                            texto_adicionado_total += 1
                            self.adicionar_log(f"  ✅ Página {page_num + 1}: texto adicionado (conf: {confidence:.2f})")
                        else:
                            self.adicionar_log(f"  ⚠️ Página {page_num + 1}: erro ao adicionar texto")
                    else:
                        self.adicionar_log(f"  ⚠️ Página {page_num + 1}: texto ignorado (conf: {confidence:.2f} < {confianca_minima:.2f})")
                else:
                    self.adicionar_log(f"  ⚠️ Página {page_num + 1}: sem dados de OCR")
            
            # Verificar se conseguimos adicionar texto
            if texto_adicionado_total == 0:
                self.adicionar_log(f"⚠️ Nenhum texto foi adicionado ao PDF. Criando PDF sem camada de texto.")
            else:
                self.adicionar_log(f"✅ Texto invisível adicionado a {texto_adicionado_total} páginas")
            
            # Salvar PDF pesquisável
            pdf_pesquisavel = os.path.join(self.pasta_destino, f"{nome_base}_pesquisavel.pdf")
            self.adicionar_log(f"💾 Salvando PDF pesquisável: {os.path.basename(pdf_pesquisavel)}")
            
            # Salvar com configurações otimizadas
            doc_novo.save(pdf_pesquisavel, 
                         garbage=4,  # Limpar objetos não utilizados
                         deflate=True,  # Compressão
                         clean=True)  # Limpar estrutura
            
            doc_novo.close()
            doc_original.close()
            
            # Verificar se o arquivo foi criado
            if os.path.exists(pdf_pesquisavel):
                # Atualizar estatísticas
                tamanho_mb = os.path.getsize(pdf_pesquisavel) / (1024 * 1024)
                self.pdfs_gerados += 1
                self.tamanho_total_mb += tamanho_mb
                self.atualizar_stats_pdf()
                
                self.adicionar_log(f"🎉 PDF pesquisável criado com sucesso!")
                self.adicionar_log(f"📁 Local: {pdf_pesquisavel}")
                self.adicionar_log(f"📏 Tamanho: {tamanho_mb:.1f} MB")
                self.adicionar_log(f"📝 Páginas com texto: {texto_adicionado_total}/{len(pages_data)}")
                
                return pdf_pesquisavel
            else:
                self.adicionar_log(f"❌ Arquivo PDF não foi criado")
                return None
            
        except Exception as e:
            self.adicionar_log(f"❌ Erro crítico no método overlay: {str(e)}")
            import traceback
            self.adicionar_log(f"🔍 Detalhes do erro: {traceback.format_exc()}")
            return None

    def adicionar_texto_invisivel_fitz(self, pagina, texto):
        """Adicionar texto invisível usando PyMuPDF - Método aprimorado"""
        try:
            if not texto or not texto.strip():
                return False
            
            # Configurações para texto invisível
            rect = pagina.rect
            
            # Limpar e preparar o texto
            texto_limpo = texto.strip()
            
            # Método 1: Tentar adicionar como bloco único (mais eficiente)
            try:
                # Usar textbox para melhor posicionamento
                text_rect = fitz.Rect(rect.x0 + 10, rect.y0 + 10, 
                                     rect.x1 - 10, rect.y1 - 10)
                
                # Inserir texto invisível como bloco
                result = pagina.insert_textbox(
                    text_rect,
                    texto_limpo,
                    fontsize=10,
                    fontname="helv",  # Helvetica
                    color=(1, 1, 1),  # Branco (invisível)
                    align=0,  # Alinhamento à esquerda
                    render_mode=3  # Modo invisível
                )
                
                if result > 0:  # Sucesso se retornar número positivo
                    return True
                    
            except Exception:
                pass  # Tentar método alternativo
            
            # Método 2: Inserir linha por linha (fallback)
            try:
                linhas = texto_limpo.split('\n')
                linhas_adicionadas = 0
                
                # Calcular espaçamento
                if len(linhas) > 0:
                    altura_linha = min(20, (rect.height - 20) / len(linhas))
                    
                    for i, linha in enumerate(linhas[:50]):  # Limitar a 50 linhas
                        if linha.strip():
                            # Posição da linha
                            y_pos = rect.y0 + 10 + (i * altura_linha)
                            
                            # Verificar se ainda está dentro dos limites da página
                            if y_pos < rect.y1 - 10:
                                # Inserir texto linha por linha
                                try:
                                    pagina.insert_text(
                                        (rect.x0 + 10, y_pos),
                                        linha.strip(),
                                        fontsize=10,
                                        fontname="helv",
                                        render_mode=3,  # Modo invisível
                                        color=(1, 1, 1)  # Branco
                                    )
                                    linhas_adicionadas += 1
                                except Exception:
                                    continue  # Continuar com próxima linha
                
                return linhas_adicionadas > 0
                
            except Exception:
                pass
            
            # Método 3: Texto único simples (último recurso)
            try:
                # Pegar apenas os primeiros 500 caracteres
                texto_resumido = texto_limpo[:500]
                
                pagina.insert_text(
                    (rect.x0 + 10, rect.y0 + 50),
                    texto_resumido,
                    fontsize=8,
                    fontname="helv",
                    render_mode=3,  # Modo invisível
                    color=(1, 1, 1)  # Branco
                )
                return True
                
            except Exception as e_final:
                self.adicionar_log(f"⚠️ Todos os métodos de texto invisível falharam: {str(e_final)}")
                return False
                
        except Exception as e:
            self.adicionar_log(f"⚠️ Erro geral ao adicionar texto invisível: {str(e)}")
            return False

    def criar_pdf_camada(self, ocr_result, caminho_pdf_original, nome_base, confianca_minima):
        """Criar PDF com nova camada de texto"""
        try:
            # Para agora, usar o método overlay
            self.adicionar_log("⚠️ Método 'layer' usando overlay como fallback")
            return self.criar_pdf_overlay(ocr_result, caminho_pdf_original, nome_base, confianca_minima)
        except Exception as e:
            self.adicionar_log(f"❌ Erro no método layer: {str(e)}")
            return None

    def atualizar_stats_pdf(self):
        """Atualizar estatísticas de PDF"""
        self.stats_pdf_gerados.config(text=f"PDFs criados: {self.pdfs_gerados}")
        self.stats_tamanho_total.config(text=f"Tamanho total: {self.tamanho_total_mb:.1f} MB")

    # === MÉTODOS DE DIVISÃO DE PDF ===
    
    def verificar_e_dividir_pdf(self, caminho_arquivo):
        """Verificar se PDF precisa ser dividido e dividir se necessário"""
        try:
            # Verificar número de páginas
            with open(caminho_arquivo, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_paginas = len(pdf_reader.pages)
            
            nome_arquivo = os.path.basename(caminho_arquivo)
            self.adicionar_log(f"📖 Analisando {nome_arquivo}: {total_paginas} páginas")
            
            # Se o arquivo tem menos páginas que o limite, processar normalmente
            if total_paginas <= self.max_paginas_divisao:
                self.adicionar_log(f"✅ Arquivo pequeno ({total_paginas} ≤ {self.max_paginas_divisao}), processando diretamente")
                return [caminho_arquivo]
            
            # Dividir em pedaços menores
            self.adicionar_log(f"📂 Arquivo grande ({total_paginas} > {self.max_paginas_divisao}), dividindo em partes...")
            return self.dividir_pdf_em_partes(caminho_arquivo, total_paginas)
            
        except Exception as e:
            self.adicionar_log(f"❌ Erro ao verificar PDF: {str(e)}")
            return [caminho_arquivo]  # Retornar arquivo original se der erro
    
    def dividir_pdf_em_partes(self, caminho_arquivo, total_paginas):
        """Dividir PDF em partes menores"""
        try:
            nome_base = os.path.splitext(os.path.basename(caminho_arquivo))[0]
            pasta_temporaria = os.path.join(self.pasta_destino, "temp_divisao")
            os.makedirs(pasta_temporaria, exist_ok=True)
            
            arquivos_divididos = []
            
            with open(caminho_arquivo, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                # Calcular número de partes
                num_partes = math.ceil(total_paginas / self.max_paginas_divisao)
                self.adicionar_log(f"📄 Dividindo em {num_partes} partes de até {self.max_paginas_divisao} páginas")
                
                for parte in range(num_partes):
                    inicio = parte * self.max_paginas_divisao
                    fim = min((parte + 1) * self.max_paginas_divisao, total_paginas)
                    
                    # Criar PDF da parte
                    pdf_writer = PyPDF2.PdfWriter()
                    
                    for pagina_num in range(inicio, fim):
                        pdf_writer.add_page(pdf_reader.pages[pagina_num])
                    
                    # Salvar parte
                    nome_parte = f"{nome_base}_parte{parte+1}_pg{inicio+1}-{fim}.pdf"
                    caminho_parte = os.path.join(pasta_temporaria, nome_parte)
                    
                    with open(caminho_parte, 'wb') as arquivo_parte:
                        pdf_writer.write(arquivo_parte)
                    
                    arquivos_divididos.append(caminho_parte)
                    self.adicionar_log(f"   ✅ Parte {parte+1}: {nome_parte} ({fim-inicio} páginas)")
            
            self.adicionar_log(f"🎯 PDF dividido em {len(arquivos_divididos)} partes com sucesso")
            return arquivos_divididos
            
        except Exception as e:
            self.adicionar_log(f"❌ Erro ao dividir PDF: {str(e)}")
            return [caminho_arquivo]
    
    def processar_arquivo_com_divisao(self, caminho_arquivo, api_key):
        """Processar arquivo com divisão automática se necessário"""
        try:
            # Verificar e dividir se necessário
            arquivos_para_processar = self.verificar_e_dividir_pdf(caminho_arquivo)
            
            if len(arquivos_para_processar) == 1:
                # Arquivo pequeno, processar normalmente
                return self.processar_arquivo_hibrido(arquivos_para_processar[0], api_key)
            
            # Arquivo foi dividido, processar cada parte
            self.adicionar_log(f"🔄 Processando {len(arquivos_para_processar)} partes separadamente...")
            
            resultados_partes = []
            sucesso_total = True
            
            for i, arquivo_parte in enumerate(arquivos_para_processar):
                if not self.processamento_ativo:
                    break
                
                nome_parte = os.path.basename(arquivo_parte)
                self.adicionar_log(f"\n📄 Processando parte {i+1}/{len(arquivos_para_processar)}: {nome_parte}")
                
                # Processar parte individual
                resultado_parte = self.processar_arquivo_hibrido(arquivo_parte, api_key)
                
                if resultado_parte:
                    resultados_partes.append(resultado_parte)
                    self.adicionar_log(f"✅ Parte {i+1} processada com sucesso")
                else:
                    self.adicionar_log(f"❌ Falha ao processar parte {i+1}")
                    sucesso_total = False
            
            # Limpar arquivos temporários
            self.limpar_arquivos_temporarios(arquivos_para_processar, caminho_arquivo)
            
            if not resultados_partes:
                return None
            
            # Consolidar resultados
            resultado_consolidado = self.consolidar_resultados_partes(resultados_partes, caminho_arquivo)
            
            if sucesso_total:
                self.adicionar_log(f"🎉 Todas as {len(arquivos_para_processar)} partes processadas com sucesso!")
            else:
                self.adicionar_log(f"⚠️ Processamento parcial: {len(resultados_partes)}/{len(arquivos_para_processar)} partes")
            
            return resultado_consolidado
            
        except Exception as e:
            self.adicionar_log(f"❌ Erro no processamento com divisão: {str(e)}")
            return None
    
    def consolidar_resultados_partes(self, resultados_partes, caminho_original):
        """Consolidar resultados de múltiplas partes em um resultado único"""
        try:
            if not resultados_partes:
                return None
            
            self.adicionar_log(f"🔗 Consolidando resultados de {len(resultados_partes)} partes...")
            
            # Começar com o primeiro resultado
            resultado_final = resultados_partes[0].copy()
            
            # Consolidar páginas
            todas_paginas = []
            pagina_offset = 0
            
            for i, resultado in enumerate(resultados_partes):
                pages = resultado.get("pages", [])
                
                # Ajustar números das páginas
                for page in pages:
                    page_copy = page.copy()
                    page_copy["page_number"] = page_copy.get("page_number", 1) + pagina_offset
                    page_copy["source_part"] = i + 1
                    todas_paginas.append(page_copy)
                
                pagina_offset += len(pages)
            
            resultado_final["pages"] = todas_paginas
            
            # Consolidar metadados
            metadata = resultado_final.get("metadata", {})
            metadata["original_file"] = os.path.basename(caminho_original)
            metadata["parts_processed"] = len(resultados_partes)
            metadata["total_pages"] = len(todas_paginas)
            metadata["method"] = f"{metadata.get('method', 'unknown')}_consolidated"
            
            # Calcular estatísticas consolidadas
            if todas_paginas:
                confidences = [p.get("confidence", 0) for p in todas_paginas]
                metadata["average_confidence"] = sum(confidences) / len(confidences)
                metadata["min_confidence"] = min(confidences)
                metadata["max_confidence"] = max(confidences)
            
            # Somar tempos de processamento
            tempo_total = sum(r.get("metadata", {}).get("processing_time", 0) for r in resultados_partes)
            metadata["processing_time"] = tempo_total
            
            resultado_final["metadata"] = metadata
            
            self.adicionar_log(f"✅ Consolidação concluída: {len(todas_paginas)} páginas totais")
            return resultado_final
            
        except Exception as e:
            self.adicionar_log(f"❌ Erro ao consolidar resultados: {str(e)}")
            return resultados_partes[0] if resultados_partes else None
    
    def limpar_arquivos_temporarios(self, arquivos_temporarios, arquivo_original):
        """Limpar arquivos temporários criados na divisão"""
        try:
            for arquivo in arquivos_temporarios:
                if arquivo != arquivo_original and os.path.exists(arquivo):
                    try:
                        os.remove(arquivo)
                    except:
                        pass  # Ignorar erros de limpeza
            
            # Tentar remover pasta temporária se estiver vazia
            pasta_temp = os.path.join(self.pasta_destino, "temp_divisao")
            if os.path.exists(pasta_temp):
                try:
                    os.rmdir(pasta_temp)
                except:
                    pass  # Pasta não está vazia ou outro erro
            
        except Exception as e:
            self.adicionar_log(f"⚠️ Aviso: erro ao limpar arquivos temporários: {str(e)}")

    # === MÉTODOS DE OCR REAL (da versão anterior) ===

    def processar_pdf_local(self, caminho_arquivo):
        """Processar PDF usando Tesseract local"""
        if not TESSERACT_AVAILABLE:
            return None, "Tesseract não disponível"
        
        nome_arquivo = os.path.basename(caminho_arquivo)
        self.adicionar_log(f"🏠 Processamento local iniciado: {nome_arquivo}")
        
        try:
            start_time = time.time()
            
            # Converter PDF para imagens
            self.adicionar_log(f"📄 Convertendo PDF para imagens...")
            pages = convert_from_path(caminho_arquivo, dpi=300)
            
            # Processar cada página
            resultados_paginas = []
            idioma = "por+eng"  # Padrão
            
            for i, page in enumerate(pages):
                self.adicionar_log(f"🔍 Processando página {i+1}/{len(pages)}")
                
                # OCR da página
                try:
                    texto = pytesseract.image_to_string(page, lang=idioma)
                except:
                    texto = pytesseract.image_to_string(page, lang='eng')
                
                # Dados da página (similar ao formato Mistral)
                confidence = self.calcular_confianca_local(page, texto)
                
                resultado_pagina = {
                    "page_number": i + 1,
                    "text": texto.strip(),
                    "markdown": f"## Página {i + 1}\n\n{texto.strip()}",
                    "confidence": confidence,
                    "processing_method": "tesseract_local"
                }
                
                resultados_paginas.append(resultado_pagina)
            
            end_time = time.time()
            duracao = end_time - start_time
            
            # Resultado final
            resultado_final = {
                "pages": resultados_paginas,
                "metadata": {
                    "total_pages": len(pages),
                    "processing_time": duracao,
                    "method": "tesseract_local",
                    "language": idioma,
                    "average_confidence": sum(p["confidence"] for p in resultados_paginas) / len(resultados_paginas) if resultados_paginas else 0
                }
            }
            
            confianca_media = resultado_final["metadata"]["average_confidence"]
            self.adicionar_log(f"✅ Processamento local concluído em {duracao:.1f}s")
            self.adicionar_log(f"📊 Confiança média: {confianca_media:.2f}")
            
            return resultado_final, None
            
        except Exception as e:
            self.adicionar_log(f"❌ Erro no processamento local: {str(e)}")
            return None, str(e)

    def calcular_confianca_local(self, image, texto):
        """Calcular uma estimativa de confiança baseada em heurísticas"""
        try:
            # Usar OCR com dados de confiança se disponível
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            
            if confidences:
                return sum(confidences) / len(confidences) / 100.0
            else:
                # Fallback: heurísticas baseadas no texto
                if not texto.strip():
                    return 0.0
                
                # Proporção de caracteres alfanuméricos
                alfa_num = sum(c.isalnum() for c in texto)
                total_chars = len(texto.replace(' ', ''))
                
                if total_chars == 0:
                    return 0.0
                
                return min(alfa_num / total_chars, 1.0)
        except:
            # Fallback simples
            return 0.5 if texto.strip() else 0.0

    def criar_sessao_robusta(self):
        """Criar sessão HTTP robusta"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST", "GET"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session

    def upload_arquivo_robusto(self, caminho_arquivo, api_key):
        """Upload robusto com timeout melhorado"""
        try:
            nome_arquivo = os.path.basename(caminho_arquivo)
            tamanho_mb = os.path.getsize(caminho_arquivo) / (1024 * 1024)
            
            # Calcular timeout baseado no tamanho do arquivo
            timeout_calculado = max(self.timeout_upload, int(tamanho_mb * 10))  # 10 segundos por MB
            
            self.adicionar_log(f"📤 Fazendo upload de {nome_arquivo} ({tamanho_mb:.1f} MB)")
            self.adicionar_log(f"⏰ Timeout configurado: {timeout_calculado} segundos")
            
            session = self.criar_sessao_robusta()
            url = "https://api.mistral.ai/v1/files"
            headers = {"Authorization": f"Bearer {api_key}"}

            with open(caminho_arquivo, "rb") as f:
                files = {"file": f}
                data = {"purpose": "ocr"}
                
                start_time = time.time()
                response = session.post(url, headers=headers, files=files, data=data, timeout=timeout_calculado)
                upload_time = time.time() - start_time

            self.adicionar_log(f"⏱️ Upload concluído em {upload_time:.1f} segundos")

            if response.status_code == 200:
                result = response.json()
                file_id = result.get("id", "unknown")
                self.adicionar_log(f"✅ Upload bem-sucedido - ID: {file_id}")
                return result
            else:
                self.adicionar_log(f"❌ Upload falhou com status: {response.status_code}")
                if response.text:
                    self.adicionar_log(f"📝 Detalhes: {response.text[:200]}...")
                return None

        except requests.exceptions.Timeout:
            self.adicionar_log(f"⏰ TIMEOUT no upload após {timeout_calculado} segundos")
            self.adicionar_log(f"💡 Arquivo muito grande ou conexão lenta")
            return None
        except Exception as e:
            self.adicionar_log(f"❌ Erro no upload: {str(e)}")
            return None

    def processar_ocr_arquivo_robusto(self, file_id, api_key, nome_arquivo=None, num_paginas=None):
        """OCR robusto com timeout inteligente"""
        try:
            nome_display = nome_arquivo or file_id
            
            # Calcular timeout baseado no número de páginas (se conhecido)
            if num_paginas:
                timeout_calculado = max(self.timeout_ocr, num_paginas * self.timeout_por_pagina)
                self.adicionar_log(f"🔍 Iniciando OCR de {nome_display} ({num_paginas} páginas)")
                self.adicionar_log(f"⏰ Timeout estimado: {timeout_calculado} segundos ({self.timeout_por_pagina}s/página)")
            else:
                timeout_calculado = self.timeout_ocr
                self.adicionar_log(f"🔍 Iniciando OCR de {nome_display}")
                self.adicionar_log(f"⏰ Timeout padrão: {timeout_calculado} segundos")
            
            session = self.criar_sessao_robusta()
            url = "https://api.mistral.ai/v1/ocr"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": "mistral-ocr-latest",
                "document": {
                    "type": "file",
                    "file_id": file_id
                }
            }

            start_time = time.time()
            self.adicionar_log(f"🚀 Enviando requisição de OCR...")
            
            response = session.post(url, headers=headers, json=payload, timeout=timeout_calculado)
            processing_time = time.time() - start_time
            
            self.adicionar_log(f"⏱️ OCR concluído em {processing_time:.1f} segundos")

            if response.status_code == 200:
                result = response.json()
                
                # Verificar se o resultado contém páginas válidas
                pages = result.get("pages", [])
                if not pages:
                    self.adicionar_log(f"⚠️ OCR retornou resultado vazio - possível problema na API")
                    return None
                
                # Contar páginas com texto válido
                paginas_com_texto = sum(1 for p in pages if p.get("text", "").strip())
                total_caracteres = sum(len(p.get("text", "")) for p in pages)
                
                self.adicionar_log(f"📊 Resultado: {len(pages)} páginas, {paginas_com_texto} com texto")
                self.adicionar_log(f"📝 Total de caracteres extraídos: {total_caracteres:,}")
                
                if total_caracteres == 0:
                    self.adicionar_log(f"⚠️ ALERTA: Nenhum texto foi extraído!")
                    self.adicionar_log(f"💡 Possíveis causas:")
                    self.adicionar_log(f"   - PDF contém apenas imagens sem texto")
                    self.adicionar_log(f"   - Qualidade das imagens muito baixa")
                    self.adicionar_log(f"   - Erro na API de OCR")
                    
                    # Ainda retornar resultado para análise
                    result["metadata"] = {
                        "method": "mistral_cloud",
                        "processing_time": processing_time,
                        "warning": "no_text_extracted",
                        "pages_processed": len(pages),
                        "characters_extracted": 0
                    }
                    return result
                
                # Adicionar metadata para compatibilidade
                if "metadata" not in result:
                    result["metadata"] = {}
                
                result["metadata"].update({
                    "method": "mistral_cloud",
                    "processing_time": processing_time,
                    "pages_processed": len(pages),
                    "pages_with_text": paginas_com_texto,
                    "characters_extracted": total_caracteres,
                    "average_confidence": self._calcular_confianca_media(pages)
                })
                
                return result
            else:
                self.adicionar_log(f"❌ OCR falhou com status: {response.status_code}")
                if response.text:
                    self.adicionar_log(f"📝 Detalhes: {response.text[:200]}...")
                
                # Tentar extrair informações do erro
                if response.status_code == 429:
                    self.adicionar_log(f"⚠️ Limite de taxa atingido - aguarde antes de tentar novamente")
                elif response.status_code == 413:
                    self.adicionar_log(f"⚠️ Arquivo muito grande para a API")
                elif response.status_code >= 500:
                    self.adicionar_log(f"⚠️ Erro interno do servidor - tente novamente mais tarde")
                
                return None

        except requests.exceptions.Timeout:
            self.adicionar_log(f"⏰ TIMEOUT no OCR após {timeout_calculado} segundos")
            self.adicionar_log(f"💡 Processamento demorou mais que o esperado")
            if num_paginas and num_paginas > 20:
                self.adicionar_log(f"💡 Considere dividir o arquivo em partes menores")
            return None
        except Exception as e:
            self.adicionar_log(f"❌ Erro no OCR: {str(e)}")
            return None
    
    def _calcular_confianca_media(self, pages):
        """Calcular confiança média das páginas"""
        if not pages:
            return 0.0
        
        confidences = []
        for page in pages:
            confidence = page.get("confidence", 0)
            if confidence > 0:
                confidences.append(confidence)
        
        return sum(confidences) / len(confidences) if confidences else 0.0

    def processar_arquivo_hibrido(self, caminho_arquivo, api_key):
        """Processar arquivo usando lógica híbrida REAL"""
        nome_arquivo = os.path.basename(caminho_arquivo)
        
        # Tentar sistema multi-engine primeiro
        if self.multi_engine_enabled and self.multi_engine_system:
            self.adicionar_log(f"🚀 Tentando sistema Multi-Engine para {nome_arquivo}")
            resultado_multi, erro_multi = self.processar_com_multi_engine(caminho_arquivo)
            
            if resultado_multi:
                self.adicionar_log(f"✅ Multi-Engine processou com sucesso")
                return resultado_multi
            else:
                self.adicionar_log(f"⚠️ Multi-Engine falhou: {erro_multi}")
                self.adicionar_log(f"🔄 Tentando método tradicional...")
        
        # Determinar estratégia de processamento (método tradicional)
        if self.usar_apenas_local or self.modo_privacidade_var.get():
            self.adicionar_log(f"🏠 Usando apenas processamento local para {nome_arquivo}")
            resultado, erro = self.processar_pdf_local(caminho_arquivo)
            
            if resultado:
                self.stats_local += 1
                self.atualizar_stats_locais()
                return resultado
            else:
                self.stats_failed += 1
                self.adicionar_log(f"❌ Falha no processamento local: {erro}")
                return None
        
        elif self.modo_local_var.get() and TESSERACT_AVAILABLE:
            self.adicionar_log(f"🔄 Tentando processamento local primeiro para {nome_arquivo}")
            resultado_local, erro_local = self.processar_pdf_local(caminho_arquivo)
            
            if resultado_local:
                confianca = resultado_local["metadata"]["average_confidence"]
                qualidade_minima = 0.7  # Padrão
                
                if confianca >= qualidade_minima:
                    self.adicionar_log(f"✅ Qualidade local suficiente ({confianca:.2f} >= {qualidade_minima:.2f})")
                    self.stats_local += 1
                    self.atualizar_stats_locais()
                    return resultado_local
                else:
                    self.adicionar_log(f"📊 Qualidade local baixa ({confianca:.2f} < {qualidade_minima:.2f})")
                    self.adicionar_log(f"☁️ Tentando processamento na nuvem...")
            else:
                self.adicionar_log(f"❌ Falha no processamento local: {erro_local}")
                self.adicionar_log(f"☁️ Tentando processamento na nuvem...")
            
            # Tentar cloud se local falhou ou qualidade insuficiente
            if api_key.strip():
                resultado_cloud = self.processar_cloud_original(caminho_arquivo, api_key)
                if resultado_cloud:
                    self.stats_cloud += 1
                    self.atualizar_stats_locais()
                    return resultado_cloud
                else:
                    self.stats_failed += 1
                    # Se cloud falhou, usar resultado local mesmo com baixa qualidade
                    if resultado_local:
                        self.adicionar_log(f"⚠ Cloud falhou, usando resultado local com baixa qualidade")
                        self.stats_local += 1
                        self.atualizar_stats_locais()
                        return resultado_local
            else:
                self.adicionar_log(f"⚠ API Key não fornecida, usando resultado local")
                if resultado_local:
                    self.stats_local += 1
                    self.atualizar_stats_locais()
                    return resultado_local
        
        else:
            # Apenas cloud
            self.adicionar_log(f"☁️ Usando apenas processamento na nuvem para {nome_arquivo}")
            if api_key.strip():
                resultado = self.processar_cloud_original(caminho_arquivo, api_key)
                if resultado:
                    self.stats_cloud += 1
                    self.atualizar_stats_locais()
                    return resultado
                else:
                    self.stats_failed += 1
            else:
                self.adicionar_log(f"❌ API Key necessária para processamento na nuvem")
                self.stats_failed += 1
        
        return None

    def processar_cloud_original(self, caminho_arquivo, api_key):
        """Processar usando o método original da nuvem com melhorias"""
        try:
            # Obter número de páginas para timeout inteligente
            num_paginas = None
            try:
                with open(caminho_arquivo, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    num_paginas = len(pdf_reader.pages)
            except:
                pass  # Se não conseguir ler, usar timeout padrão
            
            # Upload
            upload_result = self.upload_arquivo_robusto(caminho_arquivo, api_key)
            if not upload_result:
                return None
            
            file_id = upload_result.get("id")
            if not file_id:
                self.adicionar_log(f"❌ ID do arquivo não encontrado no resultado do upload")
                return None
            
            # OCR com timeout inteligente
            ocr_result = self.processar_ocr_arquivo_robusto(
                file_id, api_key, 
                nome_arquivo=os.path.basename(caminho_arquivo),
                num_paginas=num_paginas
            )
            return ocr_result
            
        except Exception as e:
            self.adicionar_log(f"❌ Erro no processamento cloud: {str(e)}")
            return None

    def salvar_resultados_completo(self, resultado, nome_arquivo_original):
        """Salvar todos os formatos de resultado"""
        try:
            nome_base = os.path.splitext(os.path.basename(nome_arquivo_original))[0]
            nome_base = nome_base.replace(" ", "_")

            os.makedirs(self.pasta_destino, exist_ok=True)
            arquivos_gerados = []

            # Adicionar metadados
            metadata = resultado.get("metadata", {})
            metadata["processed_at"] = datetime.datetime.now().isoformat()
            metadata["output_formats"] = []
            resultado["metadata"] = metadata

            # 1. Salvar JSON (se selecionado) - SEMPRE por padrão
            if self.gerar_json_var.get():
                json_filename = os.path.join(self.pasta_destino, f"{nome_base}_OCR_completo.json")
                self.adicionar_log(f"📋 Criando arquivo JSON: {os.path.basename(json_filename)}")
                
                # Melhorar a estrutura do JSON
                json_estruturado = {
                    "document_info": {
                        "filename": nome_base,
                        "processed_at": datetime.datetime.now().isoformat(),
                        "total_pages": len(resultado.get("pages", [])),
                        "processing_method": resultado.get("metadata", {}).get("method", "unknown")
                    },
                    "processing_stats": {
                        "average_confidence": resultado.get("metadata", {}).get("average_confidence", 0),
                        "processing_time": resultado.get("metadata", {}).get("processing_time", 0),
                        "language": resultado.get("metadata", {}).get("language", "unknown")
                    },
                    "pages": resultado.get("pages", []),
                    "metadata": resultado.get("metadata", {}),
                    "raw_result": resultado  # Manter resultado original para compatibilidade
                }
                
                with open(json_filename, "w", encoding="utf-8") as f:
                    json.dump(json_estruturado, f, indent=2, ensure_ascii=False)
                
                arquivos_gerados.append(("JSON", json_filename))
                metadata["output_formats"].append("JSON")
                self.adicionar_log(f"✅ JSON criado com {len(resultado.get('pages', []))} páginas")

            # 2. Salvar Markdown (se selecionado) - SEMPRE por padrão
            if self.gerar_md_var.get():
                self.adicionar_log(f"📝 Iniciando criação de Markdown...")
                md_filename = self.salvar_markdown(resultado, nome_base)
                if md_filename:
                    arquivos_gerados.append(("Markdown", md_filename))
                    metadata["output_formats"].append("Markdown")
                else:
                    self.adicionar_log(f"⚠️ Falha ao criar arquivo Markdown")

            # 3. Gerar PDF pesquisável (se selecionado) - IMPLEMENTAÇÃO CORRIGIDA
            if self.gerar_pdf_var.get():
                if PDF_GENERATION_AVAILABLE:
                    self.adicionar_log(f"🔍 Iniciando criação de PDF pesquisável...")
                    pdf_pesquisavel = self.criar_pdf_pesquisavel(resultado, nome_arquivo_original, nome_base)
                    if pdf_pesquisavel:
                        arquivos_gerados.append(("PDF Pesquisável", pdf_pesquisavel))
                        metadata["output_formats"].append("Searchable PDF")
                    else:
                        self.adicionar_log(f"⚠️ Falha ao criar PDF pesquisável")
                else:
                    self.adicionar_log(f"❌ Dependências para PDF pesquisável não estão disponíveis")
                    self.adicionar_log(f"💡 Instale: pip install reportlab PyMuPDF")

            # Log dos arquivos gerados
            self.adicionar_log(f"💾 Arquivos gerados para {nome_base}:")
            for tipo, arquivo in arquivos_gerados:
                tamanho_kb = os.path.getsize(arquivo) / 1024
                self.adicionar_log(f"   📄 {tipo}: {os.path.basename(arquivo)} ({tamanho_kb:.1f} KB)")

            return len(arquivos_gerados) > 0

        except Exception as e:
            self.adicionar_log(f"❌ Erro ao salvar resultados: {str(e)}")
            return False

    def salvar_markdown(self, resultado, nome_base):
        """Salvar resultado em formato Markdown aprimorado"""
        try:
            pages = resultado.get("pages", [])
            if not pages:
                self.adicionar_log(f"⚠️ Nenhuma página encontrada para salvar em Markdown")
                return None

            md_filename = os.path.join(self.pasta_destino, f"{nome_base}_OCR.md")
            self.adicionar_log(f"📝 Criando arquivo Markdown: {os.path.basename(md_filename)}")
            
            with open(md_filename, "w", encoding="utf-8") as f:
                # Cabeçalho principal
                f.write(f"# 📄 Resultado OCR - {nome_base}\n\n")
                
                # Informações de processamento em formato de tabela
                f.write("## 📊 Informações de Processamento\n\n")
                f.write("| Campo | Valor |\n")
                f.write("|-------|-------|\n")
                f.write(f"| **Data/Hora** | {datetime.datetime.now().strftime('%d/%m/%Y às %H:%M:%S')} |\n")
                
                # Metadados
                metadata = resultado.get("metadata", {})
                metodo = metadata.get("method", "unknown")
                
                if metodo == "tesseract_local":
                    f.write(f"| **Método** | 🏠 Processamento Local (Tesseract) |\n")
                elif metodo == "mistral_cloud":
                    f.write(f"| **Método** | ☁️ Processamento na Nuvem (Mistral AI) |\n")
                elif "hybrid" in metodo or "fallback" in metodo:
                    f.write(f"| **Método** | 🔄 Processamento Híbrido |\n")
                else:
                    f.write(f"| **Método** | {metodo} |\n")
                
                if "average_confidence" in metadata:
                    confidence = metadata['average_confidence']
                    confidence_emoji = "🟢" if confidence > 0.8 else "🟡" if confidence > 0.6 else "🔴"
                    f.write(f"| **Confiança Média** | {confidence_emoji} {confidence:.2f} ({confidence*100:.1f}%) |\n")
                
                f.write(f"| **Total de Páginas** | {len(pages)} |\n")
                
                # Informações adicionais
                if "processing_time" in metadata:
                    f.write(f"| **Tempo de Processamento** | {metadata['processing_time']:.2f} segundos |\n")
                
                if "language" in metadata:
                    f.write(f"| **Idioma** | {metadata['language']} |\n")
                
                # Informações sobre divisão de arquivo
                if "parts_processed" in metadata:
                    f.write(f"| **Partes Processadas** | {metadata['parts_processed']} (arquivo dividido) |\n")
                    f.write(f"| **Arquivo Original** | {metadata.get('original_file', 'N/A')} |\n")
                
                # Informações sobre caracteres extraídos
                if "characters_extracted" in metadata:
                    f.write(f"| **Caracteres Extraídos** | {metadata['characters_extracted']:,} |\n")
                
                # Avisos se houver
                if "warning" in metadata and metadata["warning"] == "no_text_extracted":
                    f.write(f"| **⚠️ Aviso** | Nenhum texto foi extraído das páginas |\n")
                
                # Formatos de saída
                output_formats = metadata.get("output_formats", [])
                if output_formats:
                    formats_with_icons = []
                    for fmt in output_formats:
                        if fmt == "JSON":
                            formats_with_icons.append("📋 JSON")
                        elif fmt == "Markdown":
                            formats_with_icons.append("📝 Markdown")
                        elif fmt == "Searchable PDF":
                            formats_with_icons.append("🔍 PDF Pesquisável")
                        else:
                            formats_with_icons.append(fmt)
                    f.write(f"| **Formatos Gerados** | {', '.join(formats_with_icons)} |\n")
                
                f.write("\n")
                
                # Resumo das páginas
                f.write("## 📈 Resumo das Páginas\n\n")
                total_chars = sum(len(page.get("text", "")) for page in pages)
                avg_confidence = sum(page.get("confidence", 0) for page in pages) / len(pages) if pages else 0
                
                # Contar páginas por categoria
                paginas_com_texto = sum(1 for p in pages if len(p.get("text", "").strip()) > 0)
                paginas_vazias = len(pages) - paginas_com_texto
                paginas_baixa_conf = sum(1 for p in pages if p.get("confidence", 0) < 0.5)
                
                f.write(f"- **Total de caracteres extraídos:** {total_chars:,}\n")
                f.write(f"- **Confiança média:** {avg_confidence:.2f}\n")
                f.write(f"- **Páginas processadas:** {len(pages)}\n")
                f.write(f"- **Páginas com texto:** {paginas_com_texto} / {len(pages)}\n")
                
                if paginas_vazias > 0:
                    f.write(f"- **⚠️ Páginas vazias:** {paginas_vazias}\n")
                
                if paginas_baixa_conf > 0:
                    f.write(f"- **⚠️ Páginas com baixa confiança (<0.5):** {paginas_baixa_conf}\n")
                
                # Alertas específicos
                if total_chars == 0:
                    f.write(f"\n**🚨 ALERTA: Nenhum texto foi extraído!**\n")
                    f.write(f"- Verifique se o PDF contém texto ou apenas imagens\n")
                    f.write(f"- Considere usar um arquivo de melhor qualidade\n")
                elif paginas_vazias > len(pages) * 0.5:
                    f.write(f"\n**⚠️ ATENÇÃO: Mais de 50% das páginas estão vazias**\n")
                    f.write(f"- Possível problema na qualidade do arquivo\n")
                    f.write(f"- Verifique se o processamento foi adequado\n")
                
                # Listar páginas com confiança
                f.write("\n### 📋 Lista de Páginas\n\n")
                for i, page in enumerate(pages, 1):
                    confidence = page.get("confidence", 0)
                    text_length = len(page.get("text", ""))
                    source_part = page.get("source_part")
                    
                    confidence_icon = "🟢" if confidence > 0.8 else "🟡" if confidence > 0.6 else "🔴"
                    
                    # Identificar problemas específicos
                    status_info = []
                    if text_length == 0:
                        status_info.append("❌ VAZIA")
                    elif text_length < 50:
                        status_info.append("⚠️ POUCO TEXTO")
                    
                    if confidence < 0.3:
                        status_info.append("🔴 BAIXA QUALIDADE")
                    
                    linha = f"- **Página {i}**: {confidence_icon} Confiança {confidence:.2f} | {text_length} caracteres"
                    
                    if source_part:
                        linha += f" | Parte {source_part}"
                    
                    if status_info:
                        linha += f" | {' '.join(status_info)}"
                    
                    f.write(linha + "\n")
                
                f.write("\n---\n\n")
                
                # Conteúdo das páginas
                f.write("## 📖 Conteúdo Extraído\n\n")
                
                for i, page in enumerate(pages, 1):
                    text_content = page.get("text", "") or page.get("markdown", "")
                    confidence = page.get("confidence", 0)
                    
                    # Cabeçalho da página
                    confidence_icon = "🟢" if confidence > 0.8 else "🟡" if confidence > 0.6 else "🔴"
                    f.write(f"### 📄 Página {i}")
                    if confidence > 0:
                        f.write(f" {confidence_icon} (Confiança: {confidence:.2f})")
                    f.write("\n\n")
                    
                    # Informações da página
                    if text_content.strip():
                        f.write(f"**Caracteres:** {len(text_content)} | **Linhas:** {len(text_content.splitlines())}\n\n")
                        
                        # Conteúdo formatado
                        f.write("```\n")
                        f.write(text_content.strip())
                        f.write("\n```\n\n")
                    else:
                        f.write("*⚠️ Nenhum texto foi extraído desta página.*\n\n")
                    
                    # Separador entre páginas
                    if i < len(pages):
                        f.write("---\n\n")
                
                # Rodapé
                f.write("\n---\n\n")
                f.write("*📝 Documento gerado automaticamente pelo Enhanced OCR*\n")
                f.write(f"*⏰ Processado em {datetime.datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}*\n")

            self.adicionar_log(f"✅ Markdown criado com sucesso: {os.path.basename(md_filename)}")
            return md_filename

        except Exception as e:
            self.adicionar_log(f"❌ Erro ao salvar Markdown: {str(e)}")
            import traceback
            self.adicionar_log(f"🔍 Detalhes: {traceback.format_exc()}")
            return None

    # === INTERFACE ===
    
    def criar_controles_principais(self, parent):
        """Controles principais"""
        # Título
        titulo = tk.Label(parent, text="Enhanced OCR - REAL com PDF Pesquisável", 
                         font=("Arial", 14, "bold"), fg="darkblue")
        titulo.grid(row=0, column=0, columnspan=3, pady=10)

        # API Key
        tk.Label(parent, text="API Key (Mistral):", font=("Arial", 10)).grid(
            row=1, column=0, sticky="e", padx=10, pady=8)
        self.api_key_entry = tk.Entry(parent, width=40, show="*", font=("Arial", 10))
        self.api_key_entry.grid(row=1, column=1, columnspan=2, padx=10, pady=8, sticky="ew")

        # Seleção de arquivos
        arquivo_frame = tk.LabelFrame(parent, text="Seleção de Arquivos", font=("Arial", 10, "bold"))
        arquivo_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=5)
        arquivo_frame.grid_columnconfigure(0, weight=1)

        # Botões
        button_frame = tk.Frame(arquivo_frame)
        button_frame.grid(row=0, column=0, columnspan=3, pady=5)

        self.add_files_button = tk.Button(button_frame, text="Adicionar Arquivos", 
                                         command=self.adicionar_arquivos,
                                         bg="lightblue", font=("Arial", 9))
        self.add_files_button.pack(side=tk.LEFT, padx=5)

        self.clear_files_button = tk.Button(button_frame, text="Limpar Lista", 
                                           command=self.limpar_arquivos,
                                           bg="orange", font=("Arial", 9))
        self.clear_files_button.pack(side=tk.LEFT, padx=5)

        # Lista de arquivos
        list_frame = tk.Frame(arquivo_frame)
        list_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        list_frame.grid_columnconfigure(0, weight=1)

        self.files_listbox = tk.Listbox(list_frame, height=8, font=("Arial", 9))
        self.files_listbox.grid(row=0, column=0, sticky="ew")

        scrollbar_files = tk.Scrollbar(list_frame, orient="vertical")
        scrollbar_files.grid(row=0, column=1, sticky="ns")
        self.files_listbox.config(yscrollcommand=scrollbar_files.set)
        scrollbar_files.config(command=self.files_listbox.yview)

        self.status_lote_label = tk.Label(arquivo_frame, text="Nenhum arquivo selecionado", 
                                         fg="gray", font=("Arial", 9))
        self.status_lote_label.grid(row=2, column=0, columnspan=3, pady=5)

        # Progresso e botão
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(parent, variable=self.progress_var, 
                                           maximum=100, length=300)
        self.progress_bar.grid(row=3, column=0, columnspan=3, pady=10, sticky="ew", padx=10)

        self.processar_button = tk.Button(parent, text="PROCESSAR LOTE REAL", 
                                         command=self.processar_lote_thread,
                                         bg="green", fg="white", 
                                         font=("Arial", 12, "bold"),
                                         height=2)
        self.processar_button.grid(row=4, column=0, columnspan=3, pady=15, padx=10)

        self.status_label = tk.Label(parent, text="Pronto para processar...", 
                                    fg="blue", font=("Arial", 10))
        self.status_label.grid(row=5, column=0, columnspan=3, pady=5)

    def criar_configuracoes_locais(self, parent):
        """Configurações de processamento local"""
        titulo_local = tk.Label(parent, text="OCR Local", 
                               font=("Arial", 12, "bold"), fg="darkgreen")
        titulo_local.grid(row=0, column=0, pady=10, padx=5)

        # Modo híbrido
        hibrido_frame = tk.LabelFrame(parent, text="Modo de Processamento", font=("Arial", 10, "bold"))
        hibrido_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        
        self.modo_local_var = tk.BooleanVar(value=True)
        tk.Checkbutton(hibrido_frame, text="Tentar local primeiro", 
                      variable=self.modo_local_var, font=("Arial", 9)).grid(
            row=0, column=0, sticky="w", padx=5, pady=3)

        self.modo_privacidade_var = tk.BooleanVar(value=False)
        tk.Checkbutton(hibrido_frame, text="Apenas local (privacidade)", 
                      variable=self.modo_privacidade_var, font=("Arial", 9)).grid(
            row=1, column=0, sticky="w", padx=5, pady=3)

        # Estatísticas
        stats_frame = tk.LabelFrame(parent, text="Estatísticas", font=("Arial", 10, "bold"))
        stats_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)

        self.stats_local_label = tk.Label(stats_frame, text="Local: 0", 
                                         fg="green", font=("Arial", 9))
        self.stats_local_label.grid(row=0, column=0, sticky="w", padx=5, pady=2)

        self.stats_cloud_label = tk.Label(stats_frame, text="Cloud: 0", 
                                         fg="blue", font=("Arial", 9))
        self.stats_cloud_label.grid(row=1, column=0, sticky="w", padx=5, pady=2)

        self.stats_failed_label = tk.Label(stats_frame, text="Falhas: 0", 
                                          fg="red", font=("Arial", 9))
        self.stats_failed_label.grid(row=2, column=0, sticky="w", padx=5, pady=2)

    def criar_area_log(self, parent):
        """Área de log"""
        log_title = tk.Label(parent, text="Log de Execução", 
                            font=("Arial", 11, "bold"), fg="darkred")
        log_title.grid(row=0, column=0, sticky="w", pady=(5,0), padx=5)

        self.log_text = scrolledtext.ScrolledText(parent, 
                                                 width=70, height=45,
                                                 font=("Consolas", 8),
                                                 bg="black", fg="lightgreen",
                                                 wrap=tk.WORD)
        self.log_text.grid(row=1, column=0, sticky="nsew", pady=5, padx=5)

        # Botões
        log_button_frame = tk.Frame(parent)
        log_button_frame.grid(row=2, column=0, pady=5)

        self.clear_button = tk.Button(log_button_frame, text="Limpar", 
                                     command=self.limpar_log,
                                     bg="orange", font=("Arial", 8))
        self.clear_button.pack(side=tk.LEFT, padx=2)

        self.stop_button = tk.Button(log_button_frame, text="Parar", 
                                    command=self.parar_processamento,
                                    bg="red", fg="white", font=("Arial", 8))
        self.stop_button.pack(side=tk.LEFT, padx=2)
        
        # Botão de teste das funcionalidades corrigidas
        self.test_button = tk.Button(log_button_frame, text="Testar Funcionalidades", 
                                    command=self.testar_funcionalidades_corrigidas,
                                    bg="lightgreen", font=("Arial", 8))
        self.test_button.pack(side=tk.LEFT, padx=2)
        
        # Botão de configuração MCP Workflow
        self.mcp_config_button = tk.Button(log_button_frame, text="Config MCP Workflow", 
                                          command=self.configurar_workflow_mcp,
                                          bg="lightblue", font=("Arial", 8))
        self.mcp_config_button.pack(side=tk.LEFT, padx=2)
        
        # Botão de busca inteligente
        self.search_button = tk.Button(log_button_frame, text="Busca Inteligente", 
                                      command=self.abrir_busca_inteligente,
                                      bg="lightcyan", font=("Arial", 8))
        self.search_button.pack(side=tk.LEFT, padx=2)\n        \n        # Botão de backup automático\n        self.backup_button = tk.Button(log_button_frame, text=\"Backup Automático\", \n                                      command=self.abrir_backup_manager,\n                                      bg=\"lightyellow\", font=(\"Arial\", 8))\n        self.backup_button.pack(side=tk.LEFT, padx=2)

        # Log inicial
        self.adicionar_log("=== ENHANCED OCR REAL COM PDF PESQUISÁVEL ===")
        self.adicionar_log("🔧 Verificando capacidades do sistema...")

    # === MÉTODOS DE UTILIDADE ===
    
    def adicionar_log(self, mensagem, nivel="INFO"):
        """Adicionar mensagem ao log"""
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
        log_message = f"[{timestamp}] {mensagem}"
        self.log_text.insert(tk.END, log_message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def limpar_log(self):
        """Limpar log"""
        self.log_text.delete(1.0, tk.END)
        self.adicionar_log("Log limpo pelo usuário")

    def parar_processamento(self):
        """Parar processamento"""
        self.processamento_ativo = False
        self.adicionar_log("🛑 PARADA SOLICITADA PELO USUÁRIO")
    
    def testar_funcionalidades_corrigidas(self):
        """Testar se as funcionalidades corrigidas estão funcionando"""
        self.adicionar_log("\n" + "="*50)
        self.adicionar_log("🧪 TESTANDO FUNCIONALIDADES CORRIGIDAS")
        self.adicionar_log("="*50)
        
        # 1. Testar configurações de formatos
        self.adicionar_log("📋 Teste 1: Verificando configurações de formatos de saída")
        self.adicionar_log(f"   JSON: {'✅ Ativo' if self.gerar_json_var.get() else '❌ Inativo'}")
        self.adicionar_log(f"   Markdown: {'✅ Ativo' if self.gerar_md_var.get() else '❌ Inativo'}")
        self.adicionar_log(f"   PDF Pesquisável: {'✅ Ativo' if self.gerar_pdf_var.get() else '❌ Inativo'}")
        
        # 2. Testar dependências de PDF
        self.adicionar_log("\n🔧 Teste 2: Verificando dependências de PDF pesquisável")
        pdf_ok, pdf_msg = self.verificar_dependencias_pdf()
        if pdf_ok:
            self.adicionar_log(f"   ✅ {pdf_msg}")
        else:
            self.adicionar_log(f"   ❌ {pdf_msg}")
        
        # 3. Testar criação de resultado simulado
        self.adicionar_log("\n📝 Teste 3: Testando criação de arquivos de saída")
        
        # Criar resultado simulado para teste
        resultado_teste = {
            "pages": [
                {
                    "page_number": 1,
                    "text": "Este é um texto de teste para verificar se a criação de arquivos está funcionando corretamente.\n\nEste PDF pesquisável foi gerado pelo Enhanced OCR.",
                    "confidence": 0.95,
                    "processing_method": "teste"
                },
                {
                    "page_number": 2,
                    "text": "Segunda página do documento de teste.\n\nContém texto adicional para verificar o processamento de múltiplas páginas.",
                    "confidence": 0.87,
                    "processing_method": "teste"
                }
            ],
            "metadata": {
                "method": "teste_funcionalidades",
                "average_confidence": 0.91,
                "processing_time": 1.5,
                "language": "por+eng"
            }
        }
        
        # Criar arquivo de teste temporário
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
            temp_pdf_path = temp_pdf.name
            # Criar um PDF simples de teste se reportlab estiver disponível
            if PDF_GENERATION_AVAILABLE:
                try:
                    from reportlab.pdfgen import canvas
                    from reportlab.lib.pagesizes import letter
                    
                    c = canvas.Canvas(temp_pdf_path, pagesize=letter)
                    c.drawString(100, 750, "Documento de teste do Enhanced OCR")
                    c.drawString(100, 730, "Esta é uma página de teste para verificar")
                    c.drawString(100, 710, "se a criação de PDF pesquisável está funcionando.")
                    c.showPage()
                    c.drawString(100, 750, "Segunda página de teste")
                    c.showPage()
                    c.save()
                    
                    self.adicionar_log("   ✅ PDF de teste criado")
                except Exception as e:
                    self.adicionar_log(f"   ⚠️ Erro ao criar PDF de teste: {str(e)}")
                    return
            else:
                self.adicionar_log("   ⚠️ Pulando teste de PDF - dependências não disponíveis")
                return
        
        # Testar salvamento de arquivos
        try:
            nome_base_teste = "teste_funcionalidades_corrigidas"
            
            # Forçar pasta de destino para teste
            pasta_original = self.pasta_destino
            self.pasta_destino = os.path.join(os.path.expanduser("~"), "OCR_Teste")
            os.makedirs(self.pasta_destino, exist_ok=True)
            
            self.adicionar_log(f"   📁 Pasta de teste: {self.pasta_destino}")
            
            # Testar salvamento completo
            sucesso = self.salvar_resultados_completo(resultado_teste, temp_pdf_path)
            
            if sucesso:
                self.adicionar_log("   ✅ Teste de salvamento: SUCESSO")
                
                # Verificar se os arquivos foram criados
                json_file = os.path.join(self.pasta_destino, f"{nome_base_teste}_OCR_completo.json")
                md_file = os.path.join(self.pasta_destino, f"{nome_base_teste}_OCR.md")
                pdf_file = os.path.join(self.pasta_destino, f"{nome_base_teste}_pesquisavel.pdf")
                
                self.adicionar_log("   📊 Arquivos verificados:")
                self.adicionar_log(f"      JSON: {'✅ Criado' if os.path.exists(json_file) else '❌ Não encontrado'}")
                self.adicionar_log(f"      Markdown: {'✅ Criado' if os.path.exists(md_file) else '❌ Não encontrado'}")
                self.adicionar_log(f"      PDF Pesquisável: {'✅ Criado' if os.path.exists(pdf_file) else '❌ Não encontrado'}")
                
                # Mostrar tamanhos dos arquivos
                if os.path.exists(json_file):
                    size_json = os.path.getsize(json_file) / 1024
                    self.adicionar_log(f"      JSON: {size_json:.1f} KB")
                
                if os.path.exists(md_file):
                    size_md = os.path.getsize(md_file) / 1024
                    self.adicionar_log(f"      Markdown: {size_md:.1f} KB")
                    
                if os.path.exists(pdf_file):
                    size_pdf = os.path.getsize(pdf_file) / 1024
                    self.adicionar_log(f"      PDF: {size_pdf:.1f} KB")
                
            else:
                self.adicionar_log("   ❌ Teste de salvamento: FALHOU")
            
            # Restaurar pasta original
            self.pasta_destino = pasta_original
            
        except Exception as e:
            self.adicionar_log(f"   ❌ Erro durante teste: {str(e)}")
        
        finally:
            # Limpar arquivo temporário
            try:
                os.unlink(temp_pdf_path)
            except:
                pass
        
        # 4. Resumo do teste
        self.adicionar_log("\n🎯 RESUMO DO TESTE:")
        if pdf_ok and self.gerar_json_var.get() and self.gerar_md_var.get() and self.gerar_pdf_var.get():
            self.adicionar_log("✅ TODAS AS FUNCIONALIDADES ESTÃO FUNCIONANDO!")
            self.adicionar_log("🎉 O sistema está pronto para processar PDFs com:")
            self.adicionar_log("   📋 Saída em JSON estruturado")
            self.adicionar_log("   📝 Saída em Markdown formatado")
            self.adicionar_log("   🔍 PDF pesquisável com texto invisível")
        else:
            self.adicionar_log("⚠️ Algumas funcionalidades podem não estar disponíveis")
            if not pdf_ok:
                self.adicionar_log("   💡 Instale: pip install reportlab PyMuPDF")
        
        self.adicionar_log("="*50)

    def adicionar_arquivos(self):
        """Adicionar arquivos à lista"""
        files = filedialog.askopenfilenames(
            initialdir=self.pasta_padrao,
            title="Selecione os arquivos PDF",
            filetypes=[("Arquivos PDF", "*.pdf"), ("Todos os arquivos", "*.*")]
        )
        
        for file_path in files:
            if file_path not in self.arquivos_selecionados:
                self.arquivos_selecionados.append(file_path)
                self.files_listbox.insert(tk.END, os.path.basename(file_path))
                self.adicionar_log(f"✓ Adicionado: {os.path.basename(file_path)}")
        
        self.atualizar_status_lote()

    def limpar_arquivos(self):
        """Limpar lista de arquivos"""
        self.arquivos_selecionados.clear()
        self.files_listbox.delete(0, tk.END)
        self.atualizar_status_lote()
        self.adicionar_log("Lista de arquivos limpa")

    def atualizar_status_lote(self):
        """Atualizar status dos arquivos"""
        count = len(self.arquivos_selecionados)
        if count == 0:
            self.status_lote_label.config(text="Nenhum arquivo selecionado", fg="gray")
        else:
            total_size = sum(os.path.getsize(f) for f in self.arquivos_selecionados if os.path.exists(f))
            size_mb = total_size / (1024 * 1024)
            self.status_lote_label.config(
                text=f"{count} arquivo(s) - {size_mb:.1f} MB total", 
                fg="darkgreen"
            )

    def atualizar_stats_locais(self):
        """Atualizar labels de estatísticas"""
        self.stats_local_label.config(text=f"Local: {self.stats_local}")
        self.stats_cloud_label.config(text=f"Cloud: {self.stats_cloud}")
        self.stats_failed_label.config(text=f"Falhas: {self.stats_failed}")

    def processar_lote_thread(self):
        """Thread para processamento"""
        thread = threading.Thread(target=self.processar_lote)
        thread.daemon = True
        thread.start()

    def processar_lote(self):
        """Processamento principal REAL (sem simulação)"""
        if not self.arquivos_selecionados:
            messagebox.showerror("Erro", "Nenhum arquivo selecionado.")
            return

        api_key = self.api_key_entry.get().strip()
        
        # Verificar se API key é necessária
        if not self.modo_privacidade_var.get() and not api_key and not self.modo_local_var.get():
            messagebox.showerror("Erro", "API Key necessária para processamento na nuvem.")
            return

        self.processamento_ativo = True
        self.processar_button.config(state=tk.DISABLED, text="PROCESSANDO...")
        
        self.adicionar_log("=== INICIANDO PROCESSAMENTO REAL COMPLETO ===")
        
        # Reset estatísticas
        self.stats_local = 0
        self.stats_cloud = 0
        self.stats_failed = 0
        self.pdfs_gerados = 0
        self.tamanho_total_mb = 0
        self.atualizar_stats_locais()
        self.atualizar_stats_pdf()
        
        arquivos_processados = 0
        arquivos_com_sucesso = 0
        
        for i, arquivo in enumerate(self.arquivos_selecionados):
            if not self.processamento_ativo:
                break
            
            nome_arquivo = os.path.basename(arquivo)
            self.adicionar_log(f"\n{'='*50}")
            self.adicionar_log(f"🔄 PROCESSANDO {i+1}/{len(self.arquivos_selecionados)}: {nome_arquivo}")
            
            # Progresso
            progresso = (i / len(self.arquivos_selecionados)) * 100
            self.progress_var.set(progresso)
            self.root.update_idletasks()
            
            try:
                # Processar com OCR REAL usando divisão automática
                resultado = self.processar_arquivo_com_divisao(arquivo, api_key)
                
                if resultado:
                    # Salvar todos os formatos (incluindo PDF pesquisável REAL)
                    if self.salvar_resultados_completo(resultado, arquivo):
                        self.adicionar_log(f"✅ SUCESSO COMPLETO: {nome_arquivo}")
                        arquivos_com_sucesso += 1
                        
                        # Executar workflow MCP se disponível
                        if self.workflow_enabled and self.mcp_manager:
                            try:
                                asyncio.run(self.executar_workflow_mcp(resultado, arquivo))
                            except Exception as e:
                                self.adicionar_log(f"⚠️ Workflow MCP falhou: {e}")
                    else:
                        self.adicionar_log(f"⚠️ OCR OK, mas falha ao salvar")
                else:
                    self.adicionar_log(f"❌ FALHA: {nome_arquivo}")
                
            except Exception as e:
                self.adicionar_log(f"💥 Erro inesperado: {str(e)}")
            
            arquivos_processados += 1
        
        # Finalizar
        self.progress_var.set(100)
        self.adicionar_log(f"\n{'='*50}")
        self.adicionar_log("🏁 PROCESSAMENTO CONCLUÍDO")
        self.adicionar_log(f"📊 Processados: {arquivos_processados}/{len(self.arquivos_selecionados)}")
        self.adicionar_log(f"✅ Sucessos: {arquivos_com_sucesso}")
        self.adicionar_log(f"🏠 Processamento local: {self.stats_local}")
        self.adicionar_log(f"☁️ Processamento cloud: {self.stats_cloud}")
        self.adicionar_log(f"❌ Falhas: {self.stats_failed}")
        self.adicionar_log(f"📄 PDFs pesquisáveis: {self.pdfs_gerados}")
        
        if arquivos_com_sucesso > 0:
            messagebox.showinfo("Processamento Concluído", 
                               f"Lote processado!\n\n"
                               f"✅ Sucessos: {arquivos_com_sucesso}/{arquivos_processados}\n"
                               f"🏠 Local: {self.stats_local}\n"
                               f"☁️ Cloud: {self.stats_cloud}\n"
                               f"📄 PDFs pesquisáveis: {self.pdfs_gerados}\n"
                               f"📁 Arquivos salvos em:\n{self.pasta_destino}")
        
        self.status_label.config(text=f"Concluído: {arquivos_com_sucesso}/{arquivos_processados} sucessos")
        self.processar_button.config(state=tk.NORMAL, text="PROCESSAR LOTE REAL")
        self.processamento_ativo = False

    async def executar_workflow_mcp(self, resultado, arquivo_original):
        """Executa workflow MCP após processamento OCR bem-sucedido"""
        try:
            # Converter resultado para formato WorkflowResult
            workflow_result = WorkflowResult(
                file_path=arquivo_original,
                ocr_text=self.extrair_texto_resultado(resultado),
                confidence=resultado.get("metadata", {}).get("average_confidence", 0.0),
                processing_time=resultado.get("metadata", {}).get("processing_time", 0.0),
                engine_used=resultado.get("metadata", {}).get("method", "unknown"),
                metadata=resultado.get("metadata", {}),
                pdf_searchable_path=self.get_pdf_searchable_path(arquivo_original),
                analysis_results=None
            )
            
            # Executar workflow MCP
            self.adicionar_log("🔄 Iniciando workflow MCP...")
            workflow_results = await self.mcp_manager.process_ocr_result(workflow_result)
            
            # Log dos resultados
            if workflow_results.get('workflow_executed'):
                steps = workflow_results.get('steps_executed', [])
                self.adicionar_log(f"✅ Workflow MCP concluído: {len(steps)} etapas")
                
                for step in steps:
                    self.adicionar_log(f"   ✓ {step}")
                
                # Log de erros se houver
                errors = workflow_results.get('errors', [])
                if errors:
                    self.adicionar_log(f"⚠️ Erros no workflow:")
                    for error in errors:
                        self.adicionar_log(f"   • {error}")
            else:
                reason = workflow_results.get('reason', 'Motivo desconhecido')
                self.adicionar_log(f"ℹ️ Workflow MCP não executado: {reason}")
                
        except Exception as e:
            self.adicionar_log(f"❌ Erro no workflow MCP: {str(e)}")
    
    def extrair_texto_resultado(self, resultado):
        """Extrai texto completo do resultado OCR"""
        try:
            pages = resultado.get("pages", [])
            if not pages:
                return ""
            
            texto_completo = []
            for page in pages:
                content = page.get("content", "")
                if content:
                    texto_completo.append(content)
            
            return "\n\n".join(texto_completo)
        except Exception as e:
            return f"Erro ao extrair texto: {str(e)}"
    
    def get_pdf_searchable_path(self, arquivo_original):
        """Retorna caminho do PDF pesquisável se gerado"""
        try:
            if self.gerar_pdf_var.get():
                nome_base = os.path.splitext(os.path.basename(arquivo_original))[0]
                nome_base = nome_base.replace(" ", "_")
                return os.path.join(self.pasta_destino, f"{nome_base}_pesquisavel.pdf")
            return None
        except:
            return None
    
    def configurar_workflow_mcp(self):
        """Abre janela de configuração do workflow MCP"""
        if not MCP_AVAILABLE:
            messagebox.showerror("MCP Indisponível", 
                               "Sistema MCP não está disponível.\n"
                               "Instale as dependências necessárias.")
            return
        
        config_window = tk.Toplevel(self.root)
        config_window.title("Configuração Workflow MCP")
        config_window.geometry("800x600")
        
        # Frame principal
        main_frame = ttk.Frame(config_window, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Status do workflow
        status_frame = ttk.LabelFrame(main_frame, text="Status do Workflow", padding="10")
        status_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Checkbox para ativar/desativar workflow
        self.workflow_enabled_var = tk.BooleanVar(value=self.workflow_enabled)
        ttk.Checkbutton(status_frame, text="Ativar Workflow Automatizado", 
                       variable=self.workflow_enabled_var,
                       command=self.toggle_workflow).grid(row=0, column=0, sticky=tk.W)
        
        # Status atual
        if self.mcp_manager:
            status = self.mcp_manager.get_status()
            servers_count = status.get('servers_configured', 0)
            ttk.Label(status_frame, text=f"Servidores configurados: {servers_count}").grid(row=1, column=0, sticky=tk.W)
        
        # Lista de servidores
        servers_frame = ttk.LabelFrame(main_frame, text="Servidores MCP", padding="10")
        servers_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Treeview para mostrar servidores
        columns = ('Nome', 'Tipo', 'Status')
        servers_tree = ttk.Treeview(servers_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            servers_tree.heading(col, text=col)
            servers_tree.column(col, width=100)
        
        servers_tree.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbar para a treeview
        scrollbar = ttk.Scrollbar(servers_frame, orient=tk.VERTICAL, command=servers_tree.yview)
        scrollbar.grid(row=0, column=3, sticky=(tk.N, tk.S))
        servers_tree.configure(yscrollcommand=scrollbar.set)
        
        # Botões
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0))
        
        ttk.Button(buttons_frame, text="Configurar Servidores Padrão", 
                  command=self.setup_default_mcp_servers).grid(row=0, column=0, padx=(0, 10))
        
        ttk.Button(buttons_frame, text="Fechar", 
                  command=config_window.destroy).grid(row=0, column=1)
        
        # Atualizar lista de servidores
        self.update_servers_list(servers_tree)
        
        # Configurar redimensionamento
        config_window.columnconfigure(0, weight=1)
        config_window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        servers_frame.columnconfigure(0, weight=1)
        servers_frame.rowconfigure(0, weight=1)
    
    def toggle_workflow(self):
        """Alterna ativação do workflow"""
        if self.mcp_manager:
            self.workflow_enabled = self.workflow_enabled_var.get()
            self.mcp_manager.enable_workflow(self.workflow_enabled)
            self.adicionar_log(f"🔄 Workflow MCP {'ativado' if self.workflow_enabled else 'desativado'}")
    
    def setup_default_mcp_servers(self):
        """Configura servidores MCP padrão"""
        if self.mcp_manager:
            self.mcp_manager.setup_default_servers()
            messagebox.showinfo("Sucesso", "Servidores MCP padrão configurados!\n"
                                         "Edite ~/.claude/mcp_config.json para personalizar.")
    
    def update_servers_list(self, tree):
        """Atualiza lista de servidores na interface"""
        # Limpar itens existentes
        for item in tree.get_children():
            tree.delete(item)
        
        # Adicionar servidores
        if self.mcp_manager:
            status = self.mcp_manager.get_status()
            servers = status.get('servers', {})
            
            for name, info in servers.items():
                server_type = info.get('type', 'unknown')
                enabled = info.get('enabled', False)
                status_text = 'Ativo' if enabled else 'Inativo'
                
                tree.insert('', 'end', values=(name, server_type, status_text))
    
    def abrir_busca_inteligente(self):
        """Abre interface de busca inteligente"""
        if not MCP_AVAILABLE:
            messagebox.showerror("Busca Indisponível", 
                               "Sistema de busca não está disponível.\n"
                               "Instale as dependências necessárias.")
            return
        
        try:
            # Importar interface de busca
            from src.gui.search_interface import create_search_window
            
            # Criar janela de busca
            search_window, search_interface = create_search_window(self.search_manager)
            
            self.adicionar_log("🔍 Interface de busca inteligente aberta")
            
        except Exception as e:
            self.adicionar_log(f"❌ Erro ao abrir busca inteligente: {e}")
            messagebox.showerror("Erro", f"Erro ao abrir busca inteligente:\n{str(e)}")
    
    def abrir_backup_manager(self):
        """Abre interface de gerenciamento de backup"""
        if not MCP_AVAILABLE:
            messagebox.showerror("Backup Indisponível", 
                               "Sistema de backup não está disponível.\n"
                               "Instale as dependências necessárias.")
            return
        
        try:
            # Importar interface de backup
            from src.gui.backup_interface import create_backup_window
            from src.mcp.backup_manager import BackupManager
            
            # Criar gerenciador de backup
            backup_manager = BackupManager()
            
            # Criar janela de backup
            backup_window, backup_interface = create_backup_window(backup_manager)
            
            self.adicionar_log("💾 Interface de backup automático aberta")
            
        except Exception as e:
            self.adicionar_log(f"❌ Erro ao abrir backup manager: {e}")
            messagebox.showerror("Erro", f"Erro ao abrir backup manager:\n{str(e)}")

def main():
    root = tk.Tk()
    app = OCRBatchAppComplete(root)
    root.mainloop()

if __name__ == '__main__':
    main()