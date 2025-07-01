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

class OCRBatchAppEnhancedSearchable:
    def __init__(self, root):
        self.root = root
        self.root.title("Enhanced OCR - Local + Cloud + Searchable PDF")
        self.root.geometry("1600x1000")
        self.root.resizable(True, True)

        # Configurações
        self.pasta_padrao = r"F:\OneDrive\Advocacia\ano_2025"
        self.pasta_destino = r"F:\OneDrive\Advocacia\ano_2025"
        self.max_paginas_por_lote = 200
        self.arquivos_selecionados = []
        self.processamento_ativo = False
        self.max_tentativas = 3
        self.tempo_espera_base = 60

        # Local processing settings
        self.modo_local_primeiro = True
        self.modo_privacidade = False
        self.qualidade_minima_local = 0.7
        self.usar_apenas_local = False

        # NEW: Searchable PDF settings
        self.gerar_pdf_pesquisavel = True
        self.manter_original = True
        self.qualidade_texto_pdf = 0.5

        # Criar interface
        self.criar_interface()

    def verificar_dependencias_pdf(self):
        """Verificar se dependências para PDF pesquisável estão disponíveis"""
        if not PDF_GENERATION_AVAILABLE:
            return False, "Bibliotecas não instaladas (reportlab, PyMuPDF)"
        
        try:
            # Testar importações básicas
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
        self.criar_configuracoes_pdf(pdf_frame)  # NEW
        self.criar_area_log(right_frame)

        # Verificar dependências na inicialização
        self.verificar_dependencias_inicial()

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
            ("Substituição completa", "replace")
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

        # Inicializar estatísticas
        self.pdfs_gerados = 0
        self.tamanho_total_mb = 0

    def atualizar_opcoes_pdf(self):
        """Atualizar interface baseada na seleção de PDF"""
        if self.gerar_pdf_var.get():
            self.adicionar_log("📄 Geração de PDF pesquisável ativada")
        else:
            self.adicionar_log("📄 Geração de PDF pesquisável desativada")

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
            elif metodo == "layer":
                return self.criar_pdf_camada(ocr_result, caminho_pdf_original, nome_base, confianca_minima)
            else:  # replace
                return self.criar_pdf_substituicao(ocr_result, caminho_pdf_original, nome_base, confianca_minima)
                
        except Exception as e:
            self.adicionar_log(f"❌ Erro ao criar PDF pesquisável: {str(e)}")
            return None

    def criar_pdf_overlay(self, ocr_result, caminho_pdf_original, nome_base, confianca_minima):
        """Criar PDF com texto invisível sobreposto (método mais compatível)"""
        try:
            # Abrir PDF original com PyMuPDF
            doc_original = fitz.open(caminho_pdf_original)
            
            # Criar novo documento
            doc_novo = fitz.open()
            
            pages_data = ocr_result.get("pages", [])
            
            for page_num, page_original in enumerate(doc_original):
                # Copiar página original
                nova_pagina = doc_novo.new_page(width=page_original.rect.width, 
                                               height=page_original.rect.height)
                
                # Inserir conteúdo original
                nova_pagina.show_pdf_page(nova_pagina.rect, doc_original, page_num)
                
                # Adicionar texto invisível se disponível
                if page_num < len(pages_data):
                    page_data = pages_data[page_num]
                    texto = page_data.get("text", "")
                    confidence = page_data.get("confidence", 0)
                    
                    if texto.strip() and confidence >= confianca_minima:
                        # Inserir texto invisível
                        self.adicionar_texto_invisivel_fitz(nova_pagina, texto)
                        self.adicionar_log(f"  ✅ Página {page_num + 1}: texto adicionado (conf: {confidence:.2f})")
                    else:
                        self.adicionar_log(f"  ⚠️ Página {page_num + 1}: texto ignorado (conf: {confidence:.2f})")
            
            # Salvar PDF pesquisável
            pdf_pesquisavel = os.path.join(self.pasta_destino, f"{nome_base}_pesquisavel.pdf")
            doc_novo.save(pdf_pesquisavel)
            doc_novo.close()
            doc_original.close()
            
            # Atualizar estatísticas
            tamanho_mb = os.path.getsize(pdf_pesquisavel) / (1024 * 1024)
            self.pdfs_gerados += 1
            self.tamanho_total_mb += tamanho_mb
            self.atualizar_stats_pdf()
            
            self.adicionar_log(f"✅ PDF pesquisável criado: {os.path.basename(pdf_pesquisavel)} ({tamanho_mb:.1f} MB)")
            return pdf_pesquisavel
            
        except Exception as e:
            self.adicionar_log(f"❌ Erro no método overlay: {str(e)}")
            return None

    def adicionar_texto_invisivel_fitz(self, pagina, texto):
        """Adicionar texto invisível usando PyMuPDF"""
        try:
            # Configurações para texto invisível
            rect = pagina.rect
            
            # Dividir texto em linhas para melhor distribuição
            linhas = texto.split('\n')
            altura_linha = rect.height / max(len(linhas), 1)
            
            for i, linha in enumerate(linhas):
                if linha.strip():
                    # Posição da linha
                    y_pos = rect.y0 + (i + 1) * altura_linha
                    
                    # Inserir texto invisível (renderMode 3 = invisible)
                    pagina.insert_text(
                        (rect.x0, y_pos),
                        linha.strip(),
                        fontsize=12,
                        render_mode=3,  # Modo invisível
                        color=(1, 1, 1)  # Branco (invisível)
                    )
        except Exception as e:
            self.adicionar_log(f"⚠️ Erro ao adicionar texto invisível: {str(e)}")

    def criar_pdf_camada(self, ocr_result, caminho_pdf_original, nome_base, confianca_minima):
        """Criar PDF com nova camada de texto"""
        try:
            # Para implementar futuramente - método mais avançado
            self.adicionar_log("⚠️ Método 'layer' ainda não implementado, usando overlay")
            return self.criar_pdf_overlay(ocr_result, caminho_pdf_original, nome_base, confianca_minima)
        except Exception as e:
            self.adicionar_log(f"❌ Erro no método layer: {str(e)}")
            return None

    def criar_pdf_substituicao(self, ocr_result, caminho_pdf_original, nome_base, confianca_minima):
        """Criar PDF substituindo completamente o conteúdo"""
        try:
            # Para implementar futuramente - método que substitui completamente
            self.adicionar_log("⚠️ Método 'replace' ainda não implementado, usando overlay")
            return self.criar_pdf_overlay(ocr_result, caminho_pdf_original, nome_base, confianca_minima)
        except Exception as e:
            self.adicionar_log(f"❌ Erro no método replace: {str(e)}")
            return None

    def atualizar_stats_pdf(self):
        """Atualizar estatísticas de PDF"""
        self.stats_pdf_gerados.config(text=f"PDFs criados: {self.pdfs_gerados}")
        self.stats_tamanho_total.config(text=f"Tamanho total: {self.tamanho_total_mb:.1f} MB")

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

            # 1. Salvar JSON (se selecionado)
            if self.gerar_json_var.get():
                json_filename = os.path.join(self.pasta_destino, f"{nome_base}_OCR_completo.json")
                with open(json_filename, "w", encoding="utf-8") as f:
                    json.dump(resultado, f, indent=2, ensure_ascii=False)
                arquivos_gerados.append(("JSON", json_filename))
                metadata["output_formats"].append("JSON")

            # 2. Salvar Markdown (se selecionado)
            if self.gerar_md_var.get():
                md_filename = self.salvar_markdown(resultado, nome_base)
                if md_filename:
                    arquivos_gerados.append(("Markdown", md_filename))
                    metadata["output_formats"].append("Markdown")

            # 3. Gerar PDF pesquisável (se selecionado)
            if self.gerar_pdf_var.get() and PDF_GENERATION_AVAILABLE:
                pdf_pesquisavel = self.criar_pdf_pesquisavel(resultado, nome_arquivo_original, nome_base)
                if pdf_pesquisavel:
                    arquivos_gerados.append(("PDF Pesquisável", pdf_pesquisavel))
                    metadata["output_formats"].append("Searchable PDF")

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
        """Salvar resultado em formato Markdown"""
        try:
            pages = resultado.get("pages", [])
            if not pages:
                return None

            md_filename = os.path.join(self.pasta_destino, f"{nome_base}_OCR.md")
            with open(md_filename, "w", encoding="utf-8") as f:
                f.write(f"# Resultado OCR - {nome_base}\n\n")
                f.write(f"**Data:** {time.strftime('%d/%m/%Y %H:%M:%S')}\n")
                
                # Informações de processamento
                metadata = resultado.get("metadata", {})
                metodo = metadata.get("method", "unknown")
                if metodo == "tesseract_local":
                    f.write(f"**Método:** 🏠 Processamento Local (Tesseract)\n")
                elif metodo == "mistral_cloud":
                    f.write(f"**Método:** ☁️ Processamento na Nuvem (Mistral AI)\n")
                else:
                    f.write(f"**Método:** {metodo}\n")
                
                if "average_confidence" in metadata:
                    f.write(f"**Confiança:** {metadata['average_confidence']:.2f}\n")
                
                f.write(f"**Total de páginas:** {len(pages)}\n")
                
                # Listar formatos de saída
                output_formats = metadata.get("output_formats", [])
                if output_formats:
                    f.write(f"**Formatos gerados:** {', '.join(output_formats)}\n")
                
                f.write("\n")
                
                for i, page in enumerate(pages, 1):
                    text_content = page.get("text", "") or page.get("markdown", "")
                    confidence = page.get("confidence", 0)
                    
                    f.write(f"## Página {i}")
                    if confidence > 0:
                        f.write(f" (Confiança: {confidence:.2f})")
                    f.write("\n\n")
                    
                    f.write(text_content)
                    f.write("\n\n" + "="*60 + "\n\n")

            return md_filename

        except Exception as e:
            self.adicionar_log(f"❌ Erro ao salvar Markdown: {str(e)}")
            return None

    # === MÉTODOS HERDADOS E ADAPTADOS ===
    
    def criar_controles_principais(self, parent):
        """Controles principais (adaptado da versão anterior)"""
        # Título
        titulo = tk.Label(parent, text="Enhanced OCR - Completo", 
                         font=("Arial", 14, "bold"), fg="darkblue")
        titulo.grid(row=0, column=0, columnspan=3, pady=10)

        # API Key
        tk.Label(parent, text="API Key (Mistral):", font=("Arial", 10)).grid(
            row=1, column=0, sticky="e", padx=10, pady=8)
        self.api_key_entry = tk.Entry(parent, width=40, show="*", font=("Arial", 10))
        self.api_key_entry.grid(row=1, column=1, columnspan=2, padx=10, pady=8, sticky="ew")

        # Configurações básicas
        config_frame = tk.LabelFrame(parent, text="Configurações Básicas", font=("Arial", 10, "bold"))
        config_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=10)
        config_frame.grid_columnconfigure(1, weight=1)

        tk.Label(config_frame, text="Máx. páginas:", font=("Arial", 9)).grid(
            row=0, column=0, sticky="e", padx=5, pady=5)
        self.max_paginas_entry = tk.Entry(config_frame, width=8, font=("Arial", 9))
        self.max_paginas_entry.insert(0, str(self.max_paginas_por_lote))
        self.max_paginas_entry.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        self.dividir_automatico = tk.BooleanVar(value=True)
        tk.Checkbutton(config_frame, text="Dividir automaticamente", 
                      variable=self.dividir_automatico, font=("Arial", 9)).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=5, pady=5)

        # Seleção de arquivos
        arquivo_frame = tk.LabelFrame(parent, text="Seleção de Arquivos", font=("Arial", 10, "bold"))
        arquivo_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=10, pady=5)
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
        self.progress_bar.grid(row=4, column=0, columnspan=3, pady=10, sticky="ew", padx=10)

        self.processar_button = tk.Button(parent, text="PROCESSAR LOTE", 
                                         command=self.processar_lote_thread,
                                         bg="green", fg="white", 
                                         font=("Arial", 12, "bold"),
                                         height=2)
        self.processar_button.grid(row=5, column=0, columnspan=3, pady=15, padx=10)

        self.status_label = tk.Label(parent, text="Pronto para processar...", 
                                    fg="blue", font=("Arial", 10))
        self.status_label.grid(row=6, column=0, columnspan=3, pady=5)

    def criar_configuracoes_locais(self, parent):
        """Configurações de processamento local (versão simplificada)"""
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

        # Inicializar contadores
        self.stats_local = 0
        self.stats_cloud = 0

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

        # Log inicial
        self.adicionar_log("=== ENHANCED OCR COMPLETO ===")
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

    def processar_lote_thread(self):
        """Thread para processamento"""
        thread = threading.Thread(target=self.processar_lote)
        thread.daemon = True
        thread.start()

    def processar_lote(self):
        """Processamento principal (versão simplificada para demo)"""
        if not self.arquivos_selecionados:
            messagebox.showerror("Erro", "Nenhum arquivo selecionado.")
            return

        self.processamento_ativo = True
        self.processar_button.config(state=tk.DISABLED, text="PROCESSANDO...")
        
        self.adicionar_log("=== INICIANDO PROCESSAMENTO COMPLETO ===")
        
        # Reset estatísticas
        self.stats_local = 0
        self.stats_cloud = 0
        self.pdfs_gerados = 0
        self.tamanho_total_mb = 0
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
                # DEMO: Simular processamento OCR
                # Em implementação real, usar os métodos da versão anterior
                resultado_demo = self.simular_processamento_ocr(arquivo)
                
                if resultado_demo:
                    # Salvar todos os formatos
                    if self.salvar_resultados_completo(resultado_demo, arquivo):
                        self.adicionar_log(f"✅ SUCESSO COMPLETO: {nome_arquivo}")
                        arquivos_com_sucesso += 1
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
        self.adicionar_log(f"📄 PDFs pesquisáveis: {self.pdfs_gerados}")
        
        self.status_label.config(text=f"Concluído: {arquivos_com_sucesso}/{arquivos_processados} sucessos")
        self.processar_button.config(state=tk.NORMAL, text="PROCESSAR LOTE")
        self.processamento_ativo = False

    def simular_processamento_ocr(self, arquivo):
        """Simular processamento OCR para demonstração"""
        # Esta é uma simulação - na versão real, usar os métodos OCR da versão anterior
        nome_arquivo = os.path.basename(arquivo)
        
        # Simular resultado OCR
        resultado = {
            "pages": [
                {
                    "page_number": 1,
                    "text": f"Texto simulado extraído de {nome_arquivo}\n\nEste é um exemplo de texto que seria extraído do PDF original através de OCR.\n\nO texto pode ser pesquisado e selecionado no PDF resultante.",
                    "markdown": f"# Página 1\n\nTexto simulado de {nome_arquivo}",
                    "confidence": 0.85,
                    "processing_method": "simulacao"
                }
            ],
            "metadata": {
                "total_pages": 1,
                "processing_time": 2.5,
                "method": "simulacao",
                "average_confidence": 0.85
            }
        }
        
        # Simular contadores
        self.stats_local += 1
        self.stats_local_label.config(text=f"Local: {self.stats_local}")
        
        time.sleep(1)  # Simular tempo de processamento
        return resultado

def main():
    root = tk.Tk()
    app = OCRBatchAppEnhancedSearchable(root)
    root.mainloop()

if __name__ == '__main__':
    main()