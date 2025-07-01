#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR Enhanced Hybrid - Versão com Processamento Local e Cloud
Combina Tesseract OCR (local) com Mistral AI OCR (cloud)

Funcionalidades:
- Processamento local com Tesseract OCR
- Processamento cloud com Mistral AI 
- Sistema híbrido inteligente
- Modo privacidade (somente local)
- Controle de qualidade automático
- PDF pesquisável como saída
"""

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
import subprocess
import sys

# Dependências adicionais para processamento local
try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image, ImageEnhance
    import fitz  # PyMuPDF para PDF pesquisável
    HAS_LOCAL_OCR = True
except ImportError:
    HAS_LOCAL_OCR = False

class OCRHybridApp:
    def __init__(self, root):
        self.root = root
        self.root.title("OCR Hybrid - Local + Cloud Processing")
        self.root.geometry("1600x900")
        self.root.resizable(True, True)

        # Configurações
        self.pasta_padrao = r"F:\OneDrive\Advocacia\ano_2025"
        self.pasta_destino = r"F:\OneDrive\Advocacia\ano_2025"
        self.max_paginas_por_lote = 200
        self.arquivos_selecionados = []
        self.processamento_ativo = False
        self.max_tentativas = 3
        self.tempo_espera_base = 60

        # Configurações híbridas
        self.modo_processamento = tk.StringVar(value="hybrid")  # hybrid, cloud_only, local_only, privacy
        self.confianca_minima = tk.DoubleVar(value=0.75)
        self.idioma_ocr = tk.StringVar(value="por+eng")
        self.gerar_pdf_pesquisavel = tk.BooleanVar(value=True)
        
        # Estatísticas
        self.stats_local = 0
        self.stats_cloud = 0
        self.stats_total = 0

        # Verificar dependências
        self.verificar_dependencias()
        
        # Criar interface
        self.criar_interface()

    def verificar_dependencias(self):
        """Verificar se todas as dependências estão instaladas"""
        self.tesseract_disponivel = False
        self.pdf2image_disponivel = False
        self.pymupdf_disponivel = False
        
        # Verificar Tesseract
        try:
            pytesseract.get_tesseract_version()
            self.tesseract_disponivel = True
        except:
            pass
            
        # Verificar pdf2image
        try:
            from pdf2image import convert_from_path
            self.pdf2image_disponivel = True
        except:
            pass
            
        # Verificar PyMuPDF
        try:
            import fitz
            self.pymupdf_disponivel = True
        except:
            pass

    def criar_interface(self):
        # Frame principal com layout de três colunas
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Configurar colunas: esquerda (controles), centro (configurações híbridas), direita (log)
        main_frame.grid_columnconfigure(0, weight=2)  # Controles principais
        main_frame.grid_columnconfigure(1, weight=1)  # Configurações híbridas
        main_frame.grid_columnconfigure(2, weight=1)  # Log
        main_frame.grid_rowconfigure(0, weight=1)

        # Frame esquerdo - Controles principais
        left_frame = tk.Frame(main_frame, relief="raised", bd=1)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_frame.grid_columnconfigure(1, weight=1)

        # Frame centro - Configurações híbridas
        center_frame = tk.Frame(main_frame, relief="raised", bd=1)
        center_frame.grid(row=0, column=1, sticky="nsew", padx=2)
        center_frame.grid_columnconfigure(0, weight=1)

        # Frame direito - Log
        right_frame = tk.Frame(main_frame, relief="raised", bd=1)
        right_frame.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)

        # === ÁREA ESQUERDA - CONTROLES PRINCIPAIS ===
        self.criar_controles_principais(left_frame)
        
        # === ÁREA CENTRO - CONFIGURAÇÕES HÍBRIDAS ===
        self.criar_configuracoes_hibridas(center_frame)
        
        # === ÁREA DIREITA - LOG ===
        self.criar_area_log(right_frame)

        # Log inicial
        self.adicionar_log("=== OCR HYBRID INICIADO ===")
        self.adicionar_log(f"Tesseract disponível: {'✓' if self.tesseract_disponivel else '✗'}")
        self.adicionar_log(f"pdf2image disponível: {'✓' if self.pdf2image_disponivel else '✗'}")
        self.adicionar_log(f"PyMuPDF disponível: {'✓' if self.pymupdf_disponivel else '✗'}")
        
        if not (self.tesseract_disponivel and self.pdf2image_disponivel):
            self.adicionar_log("⚠ Algumas dependências locais não estão instaladas")
            self.adicionar_log("💡 Execute: pip install pytesseract pdf2image pillow")

    def criar_controles_principais(self, parent):
        """Criar controles principais (esquerda)"""
        # Título
        titulo = tk.Label(parent, text="OCR Hybrid - Local + Cloud", 
                         font=("Arial", 14, "bold"), fg="darkblue")
        titulo.grid(row=0, column=0, columnspan=3, pady=10)

        # API Key
        tk.Label(parent, text="Mistral API Key:", font=("Arial", 10)).grid(
            row=1, column=0, sticky="e", padx=10, pady=8)
        self.api_key_entry = tk.Entry(parent, width=40, show="*", font=("Arial", 10))
        self.api_key_entry.grid(row=1, column=1, columnspan=2, padx=10, pady=8, sticky="ew")

        # Configurações básicas
        config_frame = tk.LabelFrame(parent, text="Configurações Básicas", font=("Arial", 10, "bold"))
        config_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=10)
        config_frame.grid_columnconfigure(1, weight=1)

        # Máx páginas e tentativas
        tk.Label(config_frame, text="Máx. páginas:", font=("Arial", 9)).grid(
            row=0, column=0, sticky="e", padx=5, pady=5)
        self.max_paginas_entry = tk.Entry(config_frame, width=8, font=("Arial", 9))
        self.max_paginas_entry.insert(0, str(self.max_paginas_por_lote))
        self.max_paginas_entry.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        tk.Label(config_frame, text="Máx. tentativas:", font=("Arial", 9)).grid(
            row=0, column=2, sticky="e", padx=5, pady=5)
        self.max_tentativas_entry = tk.Entry(config_frame, width=8, font=("Arial", 9))
        self.max_tentativas_entry.insert(0, str(self.max_tentativas))
        self.max_tentativas_entry.grid(row=0, column=3, sticky="w", padx=5, pady=5)

        # Opções
        self.dividir_automatico = tk.BooleanVar(value=True)
        tk.Checkbutton(config_frame, text="Dividir automaticamente", 
                      variable=self.dividir_automatico, font=("Arial", 9)).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=5, pady=5)

        self.modo_conservador = tk.BooleanVar(value=False)
        tk.Checkbutton(config_frame, text="Modo conservador", 
                      variable=self.modo_conservador, font=("Arial", 9)).grid(
            row=1, column=2, columnspan=2, sticky="w", padx=5, pady=5)

        self.log_detalhado = tk.BooleanVar(value=True)
        tk.Checkbutton(config_frame, text="Log detalhado", 
                      variable=self.log_detalhado, font=("Arial", 9)).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=5, pady=5)

        # Seleção de arquivos
        arquivo_frame = tk.LabelFrame(parent, text="Seleção de Arquivos", font=("Arial", 10, "bold"))
        arquivo_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=10, pady=5)
        arquivo_frame.grid_columnconfigure(0, weight=1)

        # Botões de seleção
        button_frame = tk.Frame(arquivo_frame)
        button_frame.grid(row=0, column=0, columnspan=3, pady=5)

        self.add_files_button = tk.Button(button_frame, text="Adicionar Arquivos", 
                                         command=self.adicionar_arquivos,
                                         bg="lightblue", font=("Arial", 9))
        self.add_files_button.pack(side=tk.LEFT, padx=5)

        self.add_folder_button = tk.Button(button_frame, text="Adicionar Pasta", 
                                          command=self.adicionar_pasta,
                                          bg="lightgreen", font=("Arial", 9))
        self.add_folder_button.pack(side=tk.LEFT, padx=5)

        self.clear_files_button = tk.Button(button_frame, text="Limpar Lista", 
                                           command=self.limpar_arquivos,
                                           bg="orange", font=("Arial", 9))
        self.clear_files_button.pack(side=tk.LEFT, padx=5)

        # Lista de arquivos
        tk.Label(arquivo_frame, text="Arquivos selecionados:", font=("Arial", 9)).grid(
            row=1, column=0, sticky="w", padx=5, pady=(10,0))

        list_frame = tk.Frame(arquivo_frame)
        list_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        list_frame.grid_columnconfigure(0, weight=1)

        self.files_listbox = tk.Listbox(list_frame, height=6, font=("Arial", 9))
        self.files_listbox.grid(row=0, column=0, sticky="ew")

        scrollbar_files = tk.Scrollbar(list_frame, orient="vertical")
        scrollbar_files.grid(row=0, column=1, sticky="ns")
        self.files_listbox.config(yscrollcommand=scrollbar_files.set)
        scrollbar_files.config(command=self.files_listbox.yview)

        self.status_lote_label = tk.Label(arquivo_frame, text="Nenhum arquivo selecionado", 
                                         fg="gray", font=("Arial", 9))
        self.status_lote_label.grid(row=3, column=0, columnspan=3, pady=5)

        # Pasta de destino
        tk.Label(parent, text="Destino:", font=("Arial", 10)).grid(
            row=4, column=0, sticky="e", padx=10, pady=8)
        destino_label = tk.Label(parent, text=self.pasta_destino, 
                                font=("Arial", 9), fg="darkgreen", 
                                relief="sunken", anchor="w")
        destino_label.grid(row=4, column=1, columnspan=2, sticky="ew", padx=10, pady=8)

        # Barra de progresso
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(parent, variable=self.progress_var, 
                                           maximum=100, length=300)
        self.progress_bar.grid(row=5, column=0, columnspan=3, pady=10, sticky="ew", padx=10)

        # Botão processar
        self.processar_button = tk.Button(parent, text="PROCESSAR HÍBRIDO", 
                                         command=self.processar_lote_thread,
                                         bg="green", fg="white", 
                                         font=("Arial", 12, "bold"),
                                         height=2)
        self.processar_button.grid(row=6, column=0, columnspan=3, pady=15, padx=10)

        # Status
        self.status_label = tk.Label(parent, text="Pronto para processar...", 
                                    fg="blue", font=("Arial", 10))
        self.status_label.grid(row=7, column=0, columnspan=3, pady=5)

    def criar_configuracoes_hibridas(self, parent):
        """Criar configurações híbridas (centro)"""
        # Título
        titulo = tk.Label(parent, text="Configurações Híbridas", 
                         font=("Arial", 12, "bold"), fg="purple")
        titulo.grid(row=0, column=0, pady=10)

        # Modo de processamento
        modo_frame = tk.LabelFrame(parent, text="Modo de Processamento", font=("Arial", 10, "bold"))
        modo_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        modo_frame.grid_columnconfigure(0, weight=1)

        tk.Radiobutton(modo_frame, text="🔄 Híbrido (Local + Cloud)", 
                      variable=self.modo_processamento, value="hybrid",
                      font=("Arial", 9)).grid(row=0, column=0, sticky="w", padx=5, pady=2)

        tk.Radiobutton(modo_frame, text="☁️ Somente Cloud (Mistral)", 
                      variable=self.modo_processamento, value="cloud_only",
                      font=("Arial", 9)).grid(row=1, column=0, sticky="w", padx=5, pady=2)

        tk.Radiobutton(modo_frame, text="💻 Somente Local (Tesseract)", 
                      variable=self.modo_processamento, value="local_only",
                      font=("Arial", 9)).grid(row=2, column=0, sticky="w", padx=5, pady=2)

        tk.Radiobutton(modo_frame, text="🔒 Privacidade (Local apenas)", 
                      variable=self.modo_processamento, value="privacy",
                      font=("Arial", 9)).grid(row=3, column=0, sticky="w", padx=5, pady=2)

        # Configurações de qualidade
        qualidade_frame = tk.LabelFrame(parent, text="Controle de Qualidade", font=("Arial", 10, "bold"))
        qualidade_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        qualidade_frame.grid_columnconfigure(1, weight=1)

        tk.Label(qualidade_frame, text="Confiança mínima:", font=("Arial", 9)).grid(
            row=0, column=0, sticky="w", padx=5, pady=5)
        
        self.confianca_scale = tk.Scale(qualidade_frame, from_=0.5, to=1.0, resolution=0.05,
                                       orient=tk.HORIZONTAL, variable=self.confianca_minima,
                                       font=("Arial", 8))
        self.confianca_scale.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        # Configurações de idioma
        idioma_frame = tk.LabelFrame(parent, text="Idioma OCR", font=("Arial", 10, "bold"))
        idioma_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=5)

        idiomas = [
            ("Português + Inglês", "por+eng"),
            ("Português", "por"),
            ("Inglês", "eng"),
            ("Espanhol", "spa"),
            ("Auto-detectar", "auto")
        ]

        for i, (texto, valor) in enumerate(idiomas):
            tk.Radiobutton(idioma_frame, text=texto, variable=self.idioma_ocr, value=valor,
                          font=("Arial", 8)).grid(row=i, column=0, sticky="w", padx=5, pady=1)

        # Opções de saída
        saida_frame = tk.LabelFrame(parent, text="Formatos de Saída", font=("Arial", 10, "bold"))
        saida_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=5)

        tk.Checkbutton(saida_frame, text="JSON (dados completos)", 
                      variable=tk.BooleanVar(value=True), font=("Arial", 9),
                      state="disabled").grid(row=0, column=0, sticky="w", padx=5, pady=2)

        tk.Checkbutton(saida_frame, text="Markdown (texto limpo)", 
                      variable=tk.BooleanVar(value=True), font=("Arial", 9),
                      state="disabled").grid(row=1, column=0, sticky="w", padx=5, pady=2)

        tk.Checkbutton(saida_frame, text="PDF Pesquisável", 
                      variable=self.gerar_pdf_pesquisavel, font=("Arial", 9)).grid(
            row=2, column=0, sticky="w", padx=5, pady=2)

        # Estatísticas
        stats_frame = tk.LabelFrame(parent, text="Estatísticas da Sessão", font=("Arial", 10, "bold"))
        stats_frame.grid(row=5, column=0, sticky="ew", padx=10, pady=5)

        self.stats_label = tk.Label(stats_frame, text="Aguardando processamento...", 
                                   font=("Arial", 9), fg="gray")
        self.stats_label.grid(row=0, column=0, padx=5, pady=5)

        # Status de dependências
        deps_frame = tk.LabelFrame(parent, text="Status das Dependências", font=("Arial", 10, "bold"))
        deps_frame.grid(row=6, column=0, sticky="ew", padx=10, pady=5)

        deps_text = f"Tesseract: {'✅' if self.tesseract_disponivel else '❌'}\n"
        deps_text += f"pdf2image: {'✅' if self.pdf2image_disponivel else '❌'}\n"
        deps_text += f"PyMuPDF: {'✅' if self.pymupdf_disponivel else '❌'}"

        tk.Label(deps_frame, text=deps_text, font=("Arial", 8), 
                justify=tk.LEFT, fg="darkgreen" if all([self.tesseract_disponivel, 
                self.pdf2image_disponivel, self.pymupdf_disponivel]) else "darkorange").grid(
            row=0, column=0, padx=5, pady=5)

        # Botão instalar dependências
        if not all([self.tesseract_disponivel, self.pdf2image_disponivel, self.pymupdf_disponivel]):
            install_button = tk.Button(deps_frame, text="Instalar Dependências", 
                                      command=self.instalar_dependencias,
                                      bg="orange", font=("Arial", 8))
            install_button.grid(row=1, column=0, pady=5)

    def criar_area_log(self, parent):
        """Criar área de log (direita)"""
        # Título do log
        log_title = tk.Label(parent, text="Log de Execução", 
                            font=("Arial", 11, "bold"), fg="darkred")
        log_title.grid(row=0, column=0, sticky="w", pady=(5,0), padx=5)

        # Área de log
        self.log_text = scrolledtext.ScrolledText(parent, 
                                                 width=50, height=35,
                                                 font=("Consolas", 8),
                                                 bg="black", fg="lightgreen",
                                                 wrap=tk.WORD)
        self.log_text.grid(row=1, column=0, sticky="nsew", pady=5, padx=5)

        # Botões do log
        log_button_frame = tk.Frame(parent)
        log_button_frame.grid(row=2, column=0, pady=5)

        self.clear_button = tk.Button(log_button_frame, text="Limpar", 
                                     command=self.limpar_log,
                                     bg="orange", font=("Arial", 8))
        self.clear_button.pack(side=tk.LEFT, padx=2)

        self.copy_button = tk.Button(log_button_frame, text="Copiar", 
                                    command=self.copiar_log,
                                    bg="lightblue", font=("Arial", 8))
        self.copy_button.pack(side=tk.LEFT, padx=2)

        self.stop_button = tk.Button(log_button_frame, text="Parar", 
                                    command=self.parar_processamento,
                                    bg="red", fg="white", font=("Arial", 8))
        self.stop_button.pack(side=tk.LEFT, padx=2)

        self.export_button = tk.Button(log_button_frame, text="Exportar", 
                                      command=self.exportar_log,
                                      bg="purple", fg="white", font=("Arial", 8))
        self.export_button.pack(side=tk.LEFT, padx=2)

    def instalar_dependencias(self):
        """Instalar dependências automaticamente"""
        def instalar():
            try:
                self.adicionar_log("🔧 Instalando dependências...")
                
                # Lista de dependências
                deps = ["pytesseract", "pdf2image", "pillow", "PyMuPDF"]
                
                for dep in deps:
                    self.adicionar_log(f"Instalando {dep}...")
                    result = subprocess.run([sys.executable, "-m", "pip", "install", dep], 
                                          capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        self.adicionar_log(f"✅ {dep} instalado com sucesso")
                    else:
                        self.adicionar_log(f"❌ Erro ao instalar {dep}: {result.stderr}")
                
                self.adicionar_log("🔄 Reinicie o programa para aplicar as mudanças")
                messagebox.showinfo("Instalação", "Dependências instaladas! Reinicie o programa.")
                
            except Exception as e:
                self.adicionar_log(f"❌ Erro na instalação: {str(e)}")
        
        thread = threading.Thread(target=instalar)
        thread.daemon = True
        thread.start()

    def adicionar_log_detalhado(self, mensagem, response=None, start_time=None, end_time=None, 
                               tentativa=None, arquivo=None, nivel="INFO"):
        """Adicionar log com informações detalhadas"""
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
        log_message = f"[{timestamp}] [{nivel}] {mensagem}"
        
        if tentativa is not None:
            log_message += f" (Tentativa {tentativa})"
        
        if arquivo is not None:
            nome_arquivo = os.path.basename(arquivo) if isinstance(arquivo, str) else str(arquivo)
            log_message += f" - Arquivo: {nome_arquivo}"
        
        if start_time and end_time:
            duracao = end_time - start_time
            log_message += f" - Duração: {duracao:.2f}s"
        
        if response is not None:
            log_message += f" - Status: {response.status_code}"
            
            if self.log_detalhado.get():
                content_type = response.headers.get('content-type', 'N/A')
                content_length = response.headers.get('content-length', 'N/A')
                log_message += f" - Content-Type: {content_type}"
                log_message += f" - Content-Length: {content_length}"
                
                try:
                    if response.status_code != 200:
                        resposta_texto = response.text[:300] if response.text else "Sem conteúdo"
                        log_message += f" - Resposta: {resposta_texto}"
                except:
                    log_message += " - Resposta: [Erro ao ler]"
        
        self.log_text.insert(tk.END, log_message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def adicionar_log(self, mensagem, nivel="INFO"):
        """Wrapper para compatibilidade"""
        self.adicionar_log_detalhado(mensagem, nivel=nivel)

    def atualizar_estatisticas(self):
        """Atualizar estatísticas na interface"""
        if self.stats_total > 0:
            pct_local = (self.stats_local / self.stats_total) * 100
            pct_cloud = (self.stats_cloud / self.stats_total) * 100
            
            stats_text = f"Total: {self.stats_total}\n"
            stats_text += f"Local: {self.stats_local} ({pct_local:.1f}%)\n"
            stats_text += f"Cloud: {self.stats_cloud} ({pct_cloud:.1f}%)"
            
            self.stats_label.config(text=stats_text, fg="darkgreen")
        else:
            self.stats_label.config(text="Aguardando processamento...", fg="gray")

    # Métodos de controle de arquivos (copiados da versão original)
    def adicionar_arquivos(self):
        """Adicionar arquivos individuais à lista"""
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

    def adicionar_pasta(self):
        """Adicionar todos os PDFs de uma pasta"""
        folder_path = filedialog.askdirectory(
            initialdir=self.pasta_padrao,
            title="Selecione a pasta com PDFs"
        )
        
        if folder_path:
            pdf_files = list(Path(folder_path).glob("*.pdf"))
            count = 0
            for pdf_file in pdf_files:
                file_path = str(pdf_file)
                if file_path not in self.arquivos_selecionados:
                    self.arquivos_selecionados.append(file_path)
                    self.files_listbox.insert(tk.END, pdf_file.name)
                    count += 1
            
            self.adicionar_log(f"✓ Adicionados {count} arquivos da pasta")
            self.atualizar_status_lote()

    def limpar_arquivos(self):
        """Limpar lista de arquivos"""
        self.arquivos_selecionados.clear()
        self.files_listbox.delete(0, tk.END)
        self.atualizar_status_lote()
        self.adicionar_log("Lista de arquivos limpa")

    def atualizar_status_lote(self):
        """Atualizar status da lista de arquivos"""
        count = len(self.arquivos_selecionados)
        if count == 0:
            self.status_lote_label.config(text="Nenhum arquivo selecionado", fg="gray")
        else:
            total_size = sum(os.path.getsize(f) for f in self.arquivos_selecionados if os.path.exists(f))
            size_mb = total_size / (1024 * 1024)
            self.status_lote_label.config(
                text=f"{count} arquivo(s) selecionado(s) - {size_mb:.1f} MB total", 
                fg="darkgreen"
            )

    def limpar_log(self):
        """Limpar a caixa de logs"""
        self.log_text.delete(1.0, tk.END)
        self.adicionar_log_detalhado("Log limpo pelo usuário")

    def copiar_log(self):
        """Copiar todo o conteúdo do log para a área de transferência"""
        try:
            log_content = self.log_text.get(1.0, tk.END)
            self.root.clipboard_clear()
            self.root.clipboard_append(log_content)
            self.adicionar_log_detalhado("Log copiado para a área de transferência")
        except Exception as e:
            self.adicionar_log_detalhado(f"Erro ao copiar log: {str(e)}", nivel="ERROR")

    def parar_processamento(self):
        """Parar o processamento em lote"""
        self.processamento_ativo = False
        self.adicionar_log_detalhado("PARADA SOLICITADA PELO USUÁRIO", nivel="WARNING")

    def exportar_log(self):
        """Exportar log detalhado para arquivo"""
        try:
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Arquivos de texto", "*.txt"), ("Todos os arquivos", "*.*")],
                initialname=f"ocr_hybrid_log_{timestamp}.txt"
            )
            
            if filename:
                log_content = self.log_text.get(1.0, tk.END)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"=== LOG OCR HYBRID ===\n")
                    f.write(f"Exportado em: {datetime.datetime.now()}\n")
                    f.write(f"Versão: Hybrid Local + Cloud\n")
                    f.write("="*50 + "\n\n")
                    f.write(log_content)
                
                self.adicionar_log_detalhado(f"Log exportado para: {filename}")
                messagebox.showinfo("Exportação", f"Log exportado com sucesso para:\n{filename}")
        except Exception as e:
            self.adicionar_log_detalhado(f"Erro ao exportar log: {str(e)}", nivel="ERROR")

    def atualizar_progresso(self, atual, total):
        """Atualizar barra de progresso"""
        if total > 0:
            progresso = (atual / total) * 100
            self.progress_var.set(progresso)
            self.root.update_idletasks()

    def processar_lote_thread(self):
        """Executar processamento em lote em thread separada"""
        thread = threading.Thread(target=self.processar_lote_hibrido)
        thread.daemon = True
        thread.start()

    def processar_lote_hibrido(self):
        """Função principal do processamento híbrido"""
        if not self.arquivos_selecionados:
            messagebox.showerror("Erro", "Nenhum arquivo selecionado.")
            return

        modo = self.modo_processamento.get()
        
        # Verificar se API key é necessária
        api_key = self.api_key_entry.get().strip()
        if modo in ["hybrid", "cloud_only"] and not api_key:
            messagebox.showerror("Erro", "API Key necessária para processamento cloud.")
            return

        # Verificar dependências locais
        if modo in ["hybrid", "local_only", "privacy"]:
            if not (self.tesseract_disponivel and self.pdf2image_disponivel):
                messagebox.showerror("Erro", "Dependências locais não instaladas.\nInstale: pytesseract, pdf2image")
                return

        self.processamento_ativo = True
        self.processar_button.config(state=tk.DISABLED, text="PROCESSANDO HÍBRIDO...")
        
        # Resetar estatísticas
        self.stats_local = 0
        self.stats_cloud = 0
        self.stats_total = 0
        
        self.adicionar_log_detalhado("=== INICIANDO PROCESSAMENTO HÍBRIDO ===")
        self.adicionar_log_detalhado(f"Modo: {modo}")
        self.adicionar_log_detalhado(f"Total de arquivos: {len(self.arquivos_selecionados)}")
        self.adicionar_log_detalhado(f"Confiança mínima: {self.confianca_minima.get()}")
        self.adicionar_log_detalhado(f"Idioma OCR: {self.idioma_ocr.get()}")
        
        arquivos_processados = 0
        arquivos_com_sucesso = 0
        
        for i, arquivo in enumerate(self.arquivos_selecionados):
            if not self.processamento_ativo:
                self.adicionar_log("🛑 PROCESSAMENTO INTERROMPIDO")
                break
            
            self.atualizar_progresso(i, len(self.arquivos_selecionados))
            nome_arquivo = os.path.basename(arquivo)
            
            self.adicionar_log(f"\n{'='*60}")
            self.adicionar_log(f"🔄 PROCESSANDO {i+1}/{len(self.arquivos_selecionados)}: {nome_arquivo}")
            self.status_label.config(text=f"Processando {i+1}/{len(self.arquivos_selecionados)}: {nome_arquivo}")
            
            try:
                sucesso = self.processar_arquivo_hibrido(arquivo, api_key, modo)
                
                if sucesso:
                    self.adicionar_log(f"✅ SUCESSO: {nome_arquivo}")
                    arquivos_com_sucesso += 1
                else:
                    self.adicionar_log(f"❌ FALHA: {nome_arquivo}")
                
                self.stats_total += 1
                self.atualizar_estatisticas()
                
            except Exception as e:
                self.adicionar_log(f"💥 Erro inesperado: {str(e)}")
            
            arquivos_processados += 1
        
        # Finalizar
        self.atualizar_progresso(len(self.arquivos_selecionados), len(self.arquivos_selecionados))
        
        self.adicionar_log(f"\n{'='*60}")
        self.adicionar_log("🏁 PROCESSAMENTO HÍBRIDO CONCLUÍDO")
        self.adicionar_log(f"📊 Processados: {arquivos_processados}/{len(self.arquivos_selecionados)}")
        self.adicionar_log(f"✅ Sucessos: {arquivos_com_sucesso}")
        self.adicionar_log(f"❌ Falhas: {arquivos_processados - arquivos_com_sucesso}")
        
        if arquivos_com_sucesso > 0:
            messagebox.showinfo("Processamento Concluído", 
                               f"Processamento híbrido concluído!\n\n"
                               f"✅ Sucessos: {arquivos_com_sucesso}/{arquivos_processados}\n"
                               f"💻 Local: {self.stats_local}\n"
                               f"☁️ Cloud: {self.stats_cloud}\n"
                               f"📁 Arquivos salvos em:\n{self.pasta_destino}")
        
        self.status_label.config(text=f"Concluído: {arquivos_com_sucesso}/{arquivos_processados} sucessos")
        self.processar_button.config(state=tk.NORMAL, text="PROCESSAR HÍBRIDO")
        self.processamento_ativo = False

    def processar_arquivo_hibrido(self, caminho_arquivo, api_key, modo):
        """Processar um arquivo usando lógica híbrida"""
        nome_arquivo = os.path.basename(caminho_arquivo)
        
        # Estratégia baseada no modo
        if modo == "cloud_only":
            return self.processar_cloud_apenas(caminho_arquivo, api_key)
        elif modo in ["local_only", "privacy"]:
            return self.processar_local_apenas(caminho_arquivo)
        elif modo == "hybrid":
            return self.processar_hibrido_inteligente(caminho_arquivo, api_key)
        
        return False

    def processar_local_apenas(self, caminho_arquivo):
        """Processar usando apenas OCR local"""
        try:
            self.adicionar_log("💻 Iniciando processamento LOCAL")
            start_time = time.time()
            
            # Converter PDF para imagens
            imagens = self.converter_pdf_para_imagens(caminho_arquivo)
            if not imagens:
                return False
            
            # Processar cada página
            resultados_paginas = []
            for i, imagem in enumerate(imagens):
                texto, confianca = self.extrair_texto_tesseract(imagem)
                
                resultados_paginas.append({
                    "page_number": i + 1,
                    "markdown": texto,
                    "confidence": confianca,
                    "method": "tesseract_local"
                })
                
                self.adicionar_log(f"  Página {i+1}: confiança {confianca:.2f}")
            
            # Criar resultado no formato padrão
            ocr_result = {
                "pages": resultados_paginas,
                "processing_method": "local_only",
                "total_pages": len(resultados_paginas),
                "processing_time": time.time() - start_time
            }
            
            # Salvar resultados
            sucesso = self.salvar_resultados_hibridos(ocr_result, caminho_arquivo)
            
            if sucesso:
                self.stats_local += 1
                end_time = time.time()
                self.adicionar_log_detalhado(f"Processamento local concluído", 
                                           start_time=start_time, end_time=end_time)
            
            return sucesso
            
        except Exception as e:
            self.adicionar_log(f"❌ Erro no processamento local: {str(e)}")
            return False

    def processar_hibrido_inteligente(self, caminho_arquivo, api_key):
        """Processar usando lógica híbrida inteligente"""
        try:
            self.adicionar_log("🔄 Iniciando processamento HÍBRIDO")
            
            # Primeiro, tentar processamento local
            self.adicionar_log("💻 Tentativa 1: Processamento local")
            start_time = time.time()
            
            imagens = self.converter_pdf_para_imagens(caminho_arquivo)
            if not imagens:
                self.adicionar_log("❌ Falha na conversão para imagens, tentando cloud")
                return self.processar_cloud_apenas(caminho_arquivo, api_key)
            
            # Processar localmente e avaliar qualidade
            resultados_paginas = []
            confianca_media = 0
            confianca_minima_threshold = self.confianca_minima.get()
            
            for i, imagem in enumerate(imagens):
                texto, confianca = self.extrair_texto_tesseract(imagem)
                confianca_media += confianca
                
                resultados_paginas.append({
                    "page_number": i + 1,
                    "markdown": texto,
                    "confidence": confianca,
                    "method": "tesseract_local"
                })
            
            confianca_media /= len(resultados_paginas)
            
            self.adicionar_log(f"💻 Processamento local concluído - Confiança média: {confianca_media:.2f}")
            
            # Decidir se usar resultado local ou tentar cloud
            if confianca_media >= confianca_minima_threshold:
                self.adicionar_log(f"✅ Qualidade local suficiente ({confianca_media:.2f} >= {confianca_minima_threshold})")
                
                ocr_result = {
                    "pages": resultados_paginas,
                    "processing_method": "hybrid_local",
                    "total_pages": len(resultados_paginas),
                    "average_confidence": confianca_media,
                    "processing_time": time.time() - start_time
                }
                
                sucesso = self.salvar_resultados_hibridos(ocr_result, caminho_arquivo)
                if sucesso:
                    self.stats_local += 1
                return sucesso
            else:
                self.adicionar_log(f"⚠ Qualidade local insuficiente ({confianca_media:.2f} < {confianca_minima_threshold})")
                self.adicionar_log("☁️ Tentativa 2: Processamento cloud como fallback")
                
                sucesso = self.processar_cloud_apenas(caminho_arquivo, api_key)
                if sucesso:
                    self.stats_cloud += 1
                return sucesso
                
        except Exception as e:
            self.adicionar_log(f"❌ Erro no processamento híbrido: {str(e)}")
            return False

    def converter_pdf_para_imagens(self, caminho_pdf):
        """Converter PDF para lista de imagens PIL"""
        try:
            if not self.pdf2image_disponivel:
                raise Exception("pdf2image não disponível")
            
            self.adicionar_log("📄 Convertendo PDF para imagens...")
            
            # Converter com configurações otimizadas
            imagens = convert_from_path(
                caminho_pdf,
                dpi=300,  # Alta resolução para melhor OCR
                fmt='PNG',
                thread_count=2
            )
            
            self.adicionar_log(f"✅ {len(imagens)} páginas convertidas")
            return imagens
            
        except Exception as e:
            self.adicionar_log(f"❌ Erro na conversão PDF→imagem: {str(e)}")
            return None

    def extrair_texto_tesseract(self, imagem):
        """Extrair texto de imagem usando Tesseract"""
        try:
            if not self.tesseract_disponivel:
                raise Exception("Tesseract não disponível")
            
            # Pré-processamento da imagem para melhor OCR
            imagem_processada = self.preprocessar_imagem(imagem)
            
            # Configurar idioma
            lang = self.idioma_ocr.get()
            if lang == "auto":
                lang = "por+eng"  # Fallback padrão
            
            # Configurações do Tesseract
            config = "--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789àáâãäèéêëìíîïòóôõöùúûüçÀÁÂÃÄÈÉÊËÌÍÎÏÒÓÔÕÖÙÚÛÜÇ.,;:!?()[]{}\"'-+*/=@#$%&_|\\~`^<> \n\t"
            
            # Extrair texto
            texto = pytesseract.image_to_string(imagem_processada, lang=lang, config=config)
            
            # Obter dados de confiança
            dados = pytesseract.image_to_data(imagem_processada, lang=lang, config=config, output_type=pytesseract.Output.DICT)
            
            # Calcular confiança média (ignorando valores -1)
            confidencias = [int(conf) for conf in dados['conf'] if int(conf) > 0]
            confianca_media = sum(confidencias) / len(confidencias) if confidencias else 0
            confianca_normalizada = confianca_media / 100.0  # Normalizar para 0-1
            
            return texto.strip(), confianca_normalizada
            
        except Exception as e:
            self.adicionar_log(f"❌ Erro no Tesseract: {str(e)}")
            return "", 0.0

    def preprocessar_imagem(self, imagem):
        """Pré-processar imagem para melhor OCR"""
        try:
            # Converter para escala de cinza
            if imagem.mode != 'L':
                imagem = imagem.convert('L')
            
            # Aumentar contraste
            enhancer = ImageEnhance.Contrast(imagem)
            imagem = enhancer.enhance(1.2)
            
            # Aumentar nitidez
            enhancer = ImageEnhance.Sharpness(imagem)
            imagem = enhancer.enhance(1.1)
            
            return imagem
            
        except Exception as e:
            self.adicionar_log(f"⚠ Erro no pré-processamento: {str(e)}")
            return imagem  # Retornar imagem original em caso de erro

    def processar_cloud_apenas(self, caminho_arquivo, api_key):
        """Processar usando apenas cloud (método original adaptado)"""
        try:
            self.adicionar_log("☁️ Iniciando processamento CLOUD")
            
            # Upload
            upload_result = self.upload_arquivo_robusto(caminho_arquivo, api_key)
            if not upload_result:
                return False
            
            file_id = upload_result.get("id")
            if not file_id:
                return False
            
            # OCR
            ocr_result = self.processar_ocr_arquivo_robusto(file_id, api_key, os.path.basename(caminho_arquivo))
            if not ocr_result:
                return False
            
            # Adicionar metadados de processamento
            ocr_result["processing_method"] = "cloud_only"
            ocr_result["api_provider"] = "mistral"
            
            # Salvar
            sucesso = self.salvar_resultados_hibridos(ocr_result, caminho_arquivo)
            if sucesso:
                self.stats_cloud += 1
            
            return sucesso
            
        except Exception as e:
            self.adicionar_log(f"❌ Erro no processamento cloud: {str(e)}")
            return False

    # Métodos da versão original (upload e OCR cloud) - mantidos para compatibilidade
    def criar_sessao_robusta(self):
        """Criar sessão HTTP ultra-robusta"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=5,
            backoff_factor=3,
            status_forcelist=[429, 500, 502, 503, 504, 520, 521, 522, 523, 524],
            allowed_methods=["POST", "GET"],
            raise_on_status=False
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=1,
            pool_maxsize=1,
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        session.headers.update({
            'User-Agent': 'OCR-Hybrid-Client/1.0',
            'Connection': 'keep-alive',
            'Accept-Encoding': 'gzip, deflate',
            'Accept': 'application/json',
            'Cache-Control': 'no-cache'
        })
        
        return session

    def upload_arquivo_robusto(self, caminho_arquivo, api_key):
        """Upload robusto (método original)"""
        max_tentativas = int(self.max_tentativas_entry.get())
        nome_arquivo = os.path.basename(caminho_arquivo)
        
        for tentativa in range(max_tentativas):
            if not self.processamento_ativo:
                return None
                
            start_time = time.time()
            
            try:
                if tentativa > 0:
                    tempo_espera = self.tempo_espera_base * (tentativa + 1) + random.randint(10, 30)
                    self.adicionar_log_detalhado(f"Aguardando {tempo_espera}s antes da próxima tentativa", 
                                               tentativa=tentativa+1, arquivo=nome_arquivo)
                    time.sleep(tempo_espera)
                
                self.adicionar_log_detalhado("Enviando arquivo para upload", 
                                           tentativa=tentativa+1, arquivo=nome_arquivo)
                
                session = self.criar_sessao_robusta()
                url = "https://api.mistral.ai/v1/files"
                headers = {"Authorization": f"Bearer {api_key}"}

                with open(caminho_arquivo, "rb") as f:
                    files = {"file": f}
                    data = {"purpose": "ocr"}
                    
                    timeout = 120 if self.modo_conservador.get() else 60
                    response = session.post(url, headers=headers, files=files, data=data, timeout=timeout)

                end_time = time.time()

                if response.status_code == 200:
                    self.adicionar_log_detalhado("Upload concluído com sucesso", response=response,
                                               start_time=start_time, end_time=end_time, 
                                               tentativa=tentativa+1, arquivo=nome_arquivo)
                    return response.json()
                elif response.status_code in [429, 502, 503, 504]:
                    self.adicionar_log_detalhado("Erro temporário no upload", response=response,
                                               start_time=start_time, end_time=end_time,
                                               tentativa=tentativa+1, arquivo=nome_arquivo, nivel="WARNING")
                    continue
                else:
                    self.adicionar_log_detalhado("Erro definitivo no upload", response=response,
                                               start_time=start_time, end_time=end_time,
                                               tentativa=tentativa+1, arquivo=nome_arquivo, nivel="ERROR")
                    return None

            except Exception as e:
                end_time = time.time()
                self.adicionar_log_detalhado(f"Erro no upload: {str(e)}", 
                                           start_time=start_time, end_time=end_time,
                                           tentativa=tentativa+1, arquivo=nome_arquivo, nivel="ERROR")
                if tentativa < max_tentativas - 1:
                    continue
                return None
        
        return None

    def processar_ocr_arquivo_robusto(self, file_id, api_key, nome_arquivo=None):
        """OCR robusto (método original)"""
        max_tentativas = int(self.max_tentativas_entry.get())
        timeouts = [300, 600, 900]
        
        for tentativa in range(max_tentativas):
            if not self.processamento_ativo:
                return None
                
            start_time = time.time()
            
            try:
                timeout_atual = timeouts[min(tentativa, len(timeouts)-1)]
                if self.modo_conservador.get():
                    timeout_atual *= 1.5
                
                if tentativa > 0:
                    tempo_espera = self.tempo_espera_base * (tentativa + 1) + random.randint(30, 60)
                    self.adicionar_log_detalhado(f"Aguardando {tempo_espera}s antes da próxima tentativa", 
                                               tentativa=tentativa+1, arquivo=nome_arquivo)
                    time.sleep(tempo_espera)
                
                self.adicionar_log_detalhado(f"Iniciando processamento OCR - Timeout: {timeout_atual}s", 
                                           tentativa=tentativa+1, arquivo=nome_arquivo)
                
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

                response = session.post(url, headers=headers, json=payload, timeout=timeout_atual)
                end_time = time.time()

                if response.status_code == 200:
                    self.adicionar_log_detalhado("OCR concluído com sucesso", response=response,
                                               start_time=start_time, end_time=end_time,
                                               tentativa=tentativa+1, arquivo=nome_arquivo)
                    return response.json()
                elif response.status_code in [429, 502, 503, 504]:
                    self.adicionar_log_detalhado("Erro temporário no OCR", response=response,
                                               start_time=start_time, end_time=end_time,
                                               tentativa=tentativa+1, arquivo=nome_arquivo, nivel="WARNING")
                    continue
                else:
                    self.adicionar_log_detalhado("Erro definitivo no OCR", response=response,
                                               start_time=start_time, end_time=end_time,
                                               tentativa=tentativa+1, arquivo=nome_arquivo, nivel="ERROR")
                    return None
                    
            except Exception as e:
                end_time = time.time()
                self.adicionar_log_detalhado(f"Erro no OCR: {str(e)}", 
                                           start_time=start_time, end_time=end_time,
                                           tentativa=tentativa+1, arquivo=nome_arquivo, nivel="ERROR")
                if tentativa < max_tentativas - 1:
                    continue
                return None
        
        return None

    def salvar_resultados_hibridos(self, ocr_result, nome_arquivo_original, parte_numero=None):
        """Salvar resultados com suporte híbrido e PDF pesquisável"""
        try:
            nome_base = os.path.splitext(os.path.basename(nome_arquivo_original))[0]
            nome_base = nome_base.replace(" ", "_")
            
            if parte_numero:
                nome_base = f"{nome_base}_subdiv_{parte_numero:02d}"

            os.makedirs(self.pasta_destino, exist_ok=True)

            # Salvar JSON (sempre)
            json_filename = os.path.join(self.pasta_destino, f"{nome_base}_OCR_hybrid.json")
            with open(json_filename, "w", encoding="utf-8") as f:
                json.dump(ocr_result, f, indent=2, ensure_ascii=False)

            # Salvar Markdown (sempre)
            pages = ocr_result.get("pages", [])
            if pages:
                md_filename = os.path.join(self.pasta_destino, f"{nome_base}_OCR.md")
                with open(md_filename, "w", encoding="utf-8") as f:
                    f.write(f"# Resultado OCR Híbrido - {nome_base}\n")
                    f.write(f"**Data:** {time.strftime('%d/%m/%Y %H:%M:%S')}\n")
                    f.write(f"**Método:** {ocr_result.get('processing_method', 'unknown')}\n")
                    
                    if 'average_confidence' in ocr_result:
                        f.write(f"**Confiança Média:** {ocr_result['average_confidence']:.2f}\n")
                    
                    f.write("\n")
                    
                    for i, page in enumerate(pages, 1):
                        # Para processamento local, usar campo 'text', para cloud usar 'markdown'
                        text_content = page.get("text", page.get("markdown", ""))
                        if text_content:
                            f.write(f"## Página {i}\n")
                            
                            # Adicionar metadados da página se disponível
                            if 'confidence' in page:
                                f.write(f"*Confiança: {page['confidence']:.2f}*\n")
                            if 'method' in page:
                                f.write(f"*Método: {page['method']}*\n")
                            f.write("\n")
                            
                            f.write(text_content)
                            f.write("\n\n" + "="*60 + "\n\n")
            else:
                # Se não há páginas estruturadas, tentar obter texto direto
                texto_direto = ocr_result.get("text", ocr_result.get("markdown", ""))
                if texto_direto:
                    md_filename = os.path.join(self.pasta_destino, f"{nome_base}_OCR.md")
                    with open(md_filename, "w", encoding="utf-8") as f:
                        f.write(f"# Resultado OCR Híbrido - {nome_base}\n")
                        f.write(f"**Data:** {time.strftime('%d/%m/%Y %H:%M:%S')}\n")
                        f.write(f"**Método:** {ocr_result.get('processing_method', 'unknown')}\n")
                        
                        if 'average_confidence' in ocr_result:
                            f.write(f"**Confiança Média:** {ocr_result['average_confidence']:.2f}\n")
                        
                        f.write("\n")
                        f.write(texto_direto)

            # Gerar PDF pesquisável se solicitado e PyMuPDF disponível
            if self.gerar_pdf_pesquisavel.get() and self.pymupdf_disponivel:
                try:
                    self.gerar_pdf_pesquisavel_func(nome_arquivo_original, ocr_result, nome_base)
                except Exception as e:
                    self.adicionar_log(f"⚠ Erro ao gerar PDF pesquisável: {str(e)}")

            self.adicionar_log(f"💾 Resultados salvos: {nome_base}")
            return True

        except Exception as e:
            self.adicionar_log(f"✗ Erro ao salvar: {str(e)}")
            return False

    def gerar_pdf_pesquisavel_func(self, pdf_original, ocr_result, nome_base):
        """Gerar PDF com texto pesquisável sobreposto"""
        try:
            if not self.pymupdf_disponivel:
                self.adicionar_log("❌ PyMuPDF não disponível para PDF pesquisável")
                return
            
            self.adicionar_log("📄 Gerando PDF pesquisável...")
            
            # Verificar se arquivo original existe
            if not os.path.exists(pdf_original):
                self.adicionar_log(f"❌ Arquivo original não encontrado: {pdf_original}")
                return
            
            # Abrir PDF original
            doc_original = fitz.open(pdf_original)
            doc_novo = fitz.open()  # PDF novo
            
            pages = ocr_result.get("pages", [])
            
            # Se não há páginas estruturadas, tentar texto direto
            if not pages:
                texto_total = ocr_result.get("text", ocr_result.get("markdown", ""))
                if texto_total:
                    # Criar estrutura de páginas artificial
                    num_paginas = len(doc_original)
                    texto_por_pagina = len(texto_total) // num_paginas if num_paginas > 0 else len(texto_total)
                    
                    for i in range(num_paginas):
                        inicio = i * texto_por_pagina
                        fim = (i + 1) * texto_por_pagina if i < num_paginas - 1 else len(texto_total)
                        pages.append({
                            "text": texto_total[inicio:fim],
                            "confidence": 0.8,
                            "method": "artificial_split"
                        })
            
            for i, page in enumerate(pages):
                if i >= len(doc_original):
                    break
                
                # Copiar página original
                doc_novo.insert_pdf(doc_original, from_page=i, to_page=i)
                page_nova = doc_novo[i]
                
                # Obter texto da página (priorizar 'text' para processamento local)
                texto = page.get("text", page.get("markdown", ""))
                if not texto.strip():
                    continue
                
                # Adicionar texto invisível (confiança mínima para incluir)
                confianca_pagina = page.get("confidence", 1.0)
                if confianca_pagina >= 0.3:  # Relaxar threshold para incluir mais texto
                    
                    # Inserir texto de forma invisível
                    rect = page_nova.rect
                    
                    # Quebrar texto em linhas para distribuir pelo PDF
                    linhas = texto.split('\n')
                    altura_linha = rect.height / max(len(linhas), 1) if len(linhas) > 1 else rect.height
                    
                    for j, linha in enumerate(linhas):
                        if linha.strip() and j < 50:  # Limitar a 50 linhas por página
                            y_pos = rect.y0 + (j * altura_linha) + 12
                            
                            # Certificar que não sai da página
                            if y_pos > rect.y1 - 12:
                                break
                            
                            # Inserir texto invisível - usar cor transparente
                            try:
                                page_nova.insert_text(
                                    (rect.x0 + 5, y_pos),
                                    linha[:200],  # Limitar tamanho da linha
                                    fontsize=0.1,  # Fonte minúscula
                                    color=(1, 1, 1),  # Branco (invisível em fundo branco)
                                    overlay=False
                                )
                            except Exception as text_error:
                                self.adicionar_log(f"⚠ Erro ao inserir linha {j}: {str(text_error)}")
                                continue
            
            # Certificar que diretório existe
            os.makedirs(self.pasta_destino, exist_ok=True)
            
            # Salvar PDF pesquisável
            pdf_filename = os.path.join(self.pasta_destino, f"{nome_base}_pesquisavel.pdf")
            doc_novo.save(pdf_filename)
            
            # Verificar se arquivo foi realmente criado
            if os.path.exists(pdf_filename):
                file_size = os.path.getsize(pdf_filename)
                self.adicionar_log(f"✅ PDF pesquisável criado: {nome_base}_pesquisavel.pdf ({file_size} bytes)")
            else:
                self.adicionar_log(f"❌ Falha ao criar PDF pesquisável: {pdf_filename}")
            
            doc_original.close()
            doc_novo.close()
            
        except Exception as e:
            self.adicionar_log(f"❌ Erro ao gerar PDF pesquisável: {str(e)}")
            import traceback
            self.adicionar_log(f"Detalhes do erro: {traceback.format_exc()}")

def main():
    root = tk.Tk()
    app = OCRHybridApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()