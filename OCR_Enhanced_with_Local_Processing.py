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

# Local OCR imports (install with: pip install pytesseract pdf2image pillow)
try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

class OCRBatchAppEnhanced:
    def __init__(self, root):
        self.root = root
        self.root.title("Enhanced OCR - Local + Cloud Processing")
        self.root.geometry("1500x900")
        self.root.resizable(True, True)

        # Configurações
        # Default folders - can be customized by end users
        self.pasta_padrao = os.path.expanduser("~/Documents/OCR_Input")
        self.pasta_destino = os.path.expanduser("~/Documents/OCR_Output")
        self.max_paginas_por_lote = 200
        self.arquivos_selecionados = []
        self.processamento_ativo = False
        self.max_tentativas = 3
        self.tempo_espera_base = 60

        # New local processing settings
        self.modo_local_primeiro = True
        self.modo_privacidade = False
        self.qualidade_minima_local = 0.7
        self.usar_apenas_local = False

        # Criar interface
        self.criar_interface()

    def verificar_tesseract(self):
        """Verificar se Tesseract está instalado e configurado"""
        if not TESSERACT_AVAILABLE:
            return False, "Bibliotecas não instaladas (pytesseract, pdf2image, pillow)"
        
        try:
            # Tentar localizar tesseract
            tesseract_path = pytesseract.pytesseract.tesseract_cmd
            if not os.path.exists(tesseract_path):
                # Tentar caminhos comuns
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
            
            # Testar versão
            version = pytesseract.get_tesseract_version()
            return True, f"Tesseract {version} encontrado em {tesseract_path}"
            
        except Exception as e:
            return False, f"Erro ao verificar Tesseract: {str(e)}"

    def criar_interface(self):
        # Frame principal com layout de três colunas
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Configurar colunas: esquerda (controles), centro (config local), direita (log)
        main_frame.grid_columnconfigure(0, weight=2)  # Controles principais
        main_frame.grid_columnconfigure(1, weight=1)  # Configurações locais
        main_frame.grid_columnconfigure(2, weight=2)  # Log
        main_frame.grid_rowconfigure(0, weight=1)

        # Frame esquerdo - Controles principais
        left_frame = tk.Frame(main_frame, relief="raised", bd=1)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_frame.grid_columnconfigure(1, weight=1)

        # Frame central - Configurações de processamento local
        center_frame = tk.Frame(main_frame, relief="raised", bd=1)
        center_frame.grid(row=0, column=1, sticky="nsew", padx=5)
        center_frame.grid_columnconfigure(0, weight=1)

        # Frame direito - Log
        right_frame = tk.Frame(main_frame, relief="raised", bd=1)
        right_frame.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)

        # === ÁREA ESQUERDA - CONTROLES EXISTENTES ===
        self.criar_controles_principais(left_frame)

        # === ÁREA CENTRAL - CONFIGURAÇÕES LOCAIS ===
        self.criar_configuracoes_locais(center_frame)

        # === ÁREA DIREITA - LOG ===
        self.criar_area_log(right_frame)

        # Verificar Tesseract na inicialização
        self.verificar_tesseract_inicial()

    def criar_controles_principais(self, parent):
        """Criar controles principais (baseado no código original)"""
        # Título
        titulo = tk.Label(parent, text="Enhanced OCR - Local + Cloud", 
                         font=("Arial", 14, "bold"), fg="darkblue")
        titulo.grid(row=0, column=0, columnspan=3, pady=10)

        # API Key
        tk.Label(parent, text="API Key (Mistral):", font=("Arial", 10)).grid(
            row=1, column=0, sticky="e", padx=10, pady=8)
        self.api_key_entry = tk.Entry(parent, width=40, show="*", font=("Arial", 10))
        self.api_key_entry.grid(row=1, column=1, columnspan=2, padx=10, pady=8, sticky="ew")

        # Configurações robustas
        config_frame = tk.LabelFrame(parent, text="Configurações de Processamento", font=("Arial", 10, "bold"))
        config_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=10)
        config_frame.grid_columnconfigure(1, weight=1)

        # Primeira linha
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

        # Segunda linha
        self.dividir_automatico = tk.BooleanVar(value=True)
        tk.Checkbutton(config_frame, text="Dividir automaticamente", 
                      variable=self.dividir_automatico, font=("Arial", 9)).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=5, pady=5)

        self.modo_conservador = tk.BooleanVar(value=False)
        tk.Checkbutton(config_frame, text="Modo conservador", 
                      variable=self.modo_conservador, font=("Arial", 9)).grid(
            row=1, column=2, columnspan=2, sticky="w", padx=5, pady=5)

        # Terceira linha
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

        # Barra de progresso
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(parent, variable=self.progress_var, 
                                           maximum=100, length=300)
        self.progress_bar.grid(row=4, column=0, columnspan=3, pady=10, sticky="ew", padx=10)

        # Botão processar
        self.processar_button = tk.Button(parent, text="PROCESSAR LOTE", 
                                         command=self.processar_lote_thread,
                                         bg="green", fg="white", 
                                         font=("Arial", 12, "bold"),
                                         height=2)
        self.processar_button.grid(row=5, column=0, columnspan=3, pady=15, padx=10)

        # Status
        self.status_label = tk.Label(parent, text="Pronto para processar...", 
                                    fg="blue", font=("Arial", 10))
        self.status_label.grid(row=6, column=0, columnspan=3, pady=5)

    def criar_configuracoes_locais(self, parent):
        """Criar área de configurações de processamento local"""
        # Título
        titulo_local = tk.Label(parent, text="Processamento Local", 
                               font=("Arial", 12, "bold"), fg="darkgreen")
        titulo_local.grid(row=0, column=0, pady=10, padx=5)

        # Status do Tesseract
        tesseract_frame = tk.LabelFrame(parent, text="Status do Tesseract", font=("Arial", 10, "bold"))
        tesseract_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        tesseract_frame.grid_columnconfigure(0, weight=1)

        self.tesseract_status_label = tk.Label(tesseract_frame, text="Verificando...", 
                                              fg="orange", font=("Arial", 9))
        self.tesseract_status_label.grid(row=0, column=0, pady=5, padx=5)

        self.verificar_tesseract_button = tk.Button(tesseract_frame, text="Verificar Novamente", 
                                                   command=self.verificar_tesseract_inicial,
                                                   bg="lightblue", font=("Arial", 8))
        self.verificar_tesseract_button.grid(row=1, column=0, pady=5)

        # Configurações de processamento híbrido
        hibrido_frame = tk.LabelFrame(parent, text="Configurações Híbridas", font=("Arial", 10, "bold"))
        hibrido_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        hibrido_frame.grid_columnconfigure(0, weight=1)

        # Modo de processamento
        self.modo_local_var = tk.BooleanVar(value=self.modo_local_primeiro)
        tk.Checkbutton(hibrido_frame, text="Tentar local primeiro", 
                      variable=self.modo_local_var, font=("Arial", 9),
                      command=self.atualizar_modo_processamento).grid(
            row=0, column=0, sticky="w", padx=5, pady=3)

        self.modo_privacidade_var = tk.BooleanVar(value=self.modo_privacidade)
        tk.Checkbutton(hibrido_frame, text="Modo privacidade (só local)", 
                      variable=self.modo_privacidade_var, font=("Arial", 9),
                      command=self.atualizar_modo_processamento).grid(
            row=1, column=0, sticky="w", padx=5, pady=3)

        self.usar_apenas_local_var = tk.BooleanVar(value=self.usar_apenas_local)
        tk.Checkbutton(hibrido_frame, text="Usar apenas local", 
                      variable=self.usar_apenas_local_var, font=("Arial", 9),
                      command=self.atualizar_modo_processamento).grid(
            row=2, column=0, sticky="w", padx=5, pady=3)

        # Configurações de qualidade
        qualidade_frame = tk.LabelFrame(parent, text="Controle de Qualidade", font=("Arial", 10, "bold"))
        qualidade_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=5)
        qualidade_frame.grid_columnconfigure(1, weight=1)

        tk.Label(qualidade_frame, text="Qualidade mín.:", font=("Arial", 9)).grid(
            row=0, column=0, sticky="e", padx=5, pady=3)
        
        self.qualidade_scale = tk.Scale(qualidade_frame, from_=0.1, to=1.0, 
                                       resolution=0.1, orient=tk.HORIZONTAL,
                                       font=("Arial", 8))
        self.qualidade_scale.set(self.qualidade_minima_local)
        self.qualidade_scale.grid(row=0, column=1, sticky="ew", padx=5, pady=3)

        # Idiomas disponíveis
        idioma_frame = tk.LabelFrame(parent, text="Idiomas Tesseract", font=("Arial", 10, "bold"))
        idioma_frame.grid(row=4, column=0, sticky="ew", padx=5, pady=5)
        idioma_frame.grid_columnconfigure(0, weight=1)

        self.idioma_var = tk.StringVar(value="por+eng")
        idiomas = [("Português + Inglês", "por+eng"), ("Português", "por"), 
                  ("Inglês", "eng"), ("Auto", "auto")]
        
        for i, (texto, valor) in enumerate(idiomas):
            tk.Radiobutton(idioma_frame, text=texto, variable=self.idioma_var, 
                          value=valor, font=("Arial", 8)).grid(
                row=i, column=0, sticky="w", padx=5, pady=1)

        # Estatísticas
        stats_frame = tk.LabelFrame(parent, text="Estatísticas da Sessão", font=("Arial", 10, "bold"))
        stats_frame.grid(row=5, column=0, sticky="ew", padx=5, pady=5)
        stats_frame.grid_columnconfigure(1, weight=1)

        self.stats_local_label = tk.Label(stats_frame, text="Local: 0", 
                                         fg="green", font=("Arial", 9))
        self.stats_local_label.grid(row=0, column=0, sticky="w", padx=5, pady=2)

        self.stats_cloud_label = tk.Label(stats_frame, text="Cloud: 0", 
                                         fg="blue", font=("Arial", 9))
        self.stats_cloud_label.grid(row=1, column=0, sticky="w", padx=5, pady=2)

        self.stats_failed_label = tk.Label(stats_frame, text="Falhas: 0", 
                                          fg="red", font=("Arial", 9))
        self.stats_failed_label.grid(row=2, column=0, sticky="w", padx=5, pady=2)

        # Inicializar estatísticas
        self.stats_local = 0
        self.stats_cloud = 0
        self.stats_failed = 0

    def criar_area_log(self, parent):
        """Criar área de log (baseado no código original)"""
        # Título do log
        log_title = tk.Label(parent, text="Log de Execução", 
                            font=("Arial", 11, "bold"), fg="darkred")
        log_title.grid(row=0, column=0, sticky="w", pady=(5,0), padx=5)

        # Área de log
        self.log_text = scrolledtext.ScrolledText(parent, 
                                                 width=70, height=40,
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

        # Log inicial
        self.adicionar_log("=== ENHANCED OCR COM PROCESSAMENTO LOCAL ===")
        self.adicionar_log("🔧 Verificando capacidades do sistema...")

    def verificar_tesseract_inicial(self):
        """Verificar Tesseract na inicialização"""
        def verificar():
            disponivel, mensagem = self.verificar_tesseract()
            
            if disponivel:
                self.tesseract_status_label.config(text="✓ Tesseract disponível", fg="green")
                self.adicionar_log(f"✓ {mensagem}")
                
                # Verificar idiomas disponíveis
                try:
                    idiomas = pytesseract.get_languages()
                    self.adicionar_log(f"📋 Idiomas disponíveis: {', '.join(idiomas)}")
                except:
                    self.adicionar_log("⚠ Não foi possível listar idiomas")
            else:
                self.tesseract_status_label.config(text="✗ Tesseract indisponível", fg="red")
                self.adicionar_log(f"✗ {mensagem}")
                self.adicionar_log("💡 Para instalar:")
                self.adicionar_log("   Linux: sudo apt install tesseract-ocr tesseract-ocr-por")
                self.adicionar_log("   pip install pytesseract pdf2image pillow")
        
        thread = threading.Thread(target=verificar)
        thread.daemon = True
        thread.start()

    def atualizar_modo_processamento(self):
        """Atualizar configurações baseadas nos checkboxes"""
        self.modo_local_primeiro = self.modo_local_var.get()
        self.modo_privacidade = self.modo_privacidade_var.get()
        self.usar_apenas_local = self.usar_apenas_local_var.get()
        
        # Se modo privacidade está ativo, desabilitar cloud
        if self.modo_privacidade:
            self.usar_apenas_local_var.set(True)
            self.usar_apenas_local = True
        
        # Log da mudança
        if self.modo_privacidade:
            self.adicionar_log("🔒 Modo privacidade ativado - apenas processamento local")
        elif self.usar_apenas_local:
            self.adicionar_log("🏠 Usando apenas processamento local")
        elif self.modo_local_primeiro:
            self.adicionar_log("🔄 Modo híbrido - local primeiro, depois cloud")
        else:
            self.adicionar_log("☁️ Usando apenas processamento cloud")

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
            idioma = self.idioma_var.get()
            
            for i, page in enumerate(pages):
                self.adicionar_log(f"🔍 Processando página {i+1}/{len(pages)}")
                
                # OCR da página
                if idioma == "auto":
                    # Tentar detectar idioma automaticamente
                    try:
                        texto = pytesseract.image_to_string(page, lang='por+eng')
                    except:
                        texto = pytesseract.image_to_string(page, lang='eng')
                else:
                    texto = pytesseract.image_to_string(page, lang=idioma)
                
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

    def processar_arquivo_hibrido(self, caminho_arquivo, api_key):
        """Processar arquivo usando lógica híbrida"""
        nome_arquivo = os.path.basename(caminho_arquivo)
        
        # Determinar estratégia de processamento
        if self.usar_apenas_local or self.modo_privacidade:
            self.adicionar_log(f"🏠 Usando apenas processamento local para {nome_arquivo}")
            resultado, erro = self.processar_pdf_local(caminho_arquivo)
            
            if resultado:
                self.stats_local += 1
                self.atualizar_estatisticas()
                return resultado
            else:
                self.stats_failed += 1
                self.atualizar_estatisticas()
                self.adicionar_log(f"❌ Falha no processamento local: {erro}")
                return None
        
        elif self.modo_local_primeiro and TESSERACT_AVAILABLE:
            self.adicionar_log(f"🔄 Tentando processamento local primeiro para {nome_arquivo}")
            resultado_local, erro_local = self.processar_pdf_local(caminho_arquivo)
            
            if resultado_local:
                confianca = resultado_local["metadata"]["average_confidence"]
                qualidade_minima = self.qualidade_scale.get()
                
                if confianca >= qualidade_minima:
                    self.adicionar_log(f"✅ Qualidade local suficiente ({confianca:.2f} >= {qualidade_minima:.2f})")
                    self.stats_local += 1
                    self.atualizar_estatisticas()
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
                    self.atualizar_estatisticas()
                    return resultado_cloud
                else:
                    self.stats_failed += 1
                    self.atualizar_estatisticas()
                    # Se cloud falhou, usar resultado local mesmo com baixa qualidade
                    if resultado_local:
                        self.adicionar_log(f"⚠ Cloud falhou, usando resultado local com baixa qualidade")
                        self.stats_local += 1
                        self.atualizar_estatisticas()
                        return resultado_local
            else:
                self.adicionar_log(f"⚠ API Key não fornecida, usando resultado local")
                if resultado_local:
                    self.stats_local += 1
                    self.atualizar_estatisticas()
                    return resultado_local
        
        else:
            # Apenas cloud
            self.adicionar_log(f"☁️ Usando apenas processamento na nuvem para {nome_arquivo}")
            if api_key.strip():
                resultado = self.processar_cloud_original(caminho_arquivo, api_key)
                if resultado:
                    self.stats_cloud += 1
                    self.atualizar_estatisticas()
                    return resultado
                else:
                    self.stats_failed += 1
                    self.atualizar_estatisticas()
            else:
                self.adicionar_log(f"❌ API Key necessária para processamento na nuvem")
                self.stats_failed += 1
                self.atualizar_estatisticas()
        
        return None

    def processar_cloud_original(self, caminho_arquivo, api_key):
        """Processar usando o método original da nuvem"""
        # Upload
        upload_result = self.upload_arquivo_robusto(caminho_arquivo, api_key)
        if not upload_result:
            return None
        
        file_id = upload_result.get("id")
        if not file_id:
            return None
        
        # OCR
        ocr_result = self.processar_ocr_arquivo_robusto(file_id, api_key, os.path.basename(caminho_arquivo))
        return ocr_result

    def atualizar_estatisticas(self):
        """Atualizar labels de estatísticas"""
        self.stats_local_label.config(text=f"Local: {self.stats_local}")
        self.stats_cloud_label.config(text=f"Cloud: {self.stats_cloud}")
        self.stats_failed_label.config(text=f"Falhas: {self.stats_failed}")

    # === MÉTODOS DO CÓDIGO ORIGINAL (adaptados) ===
    
    def adicionar_log(self, mensagem, nivel="INFO"):
        """Adicionar mensagem ao log"""
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
        log_message = f"[{timestamp}] {mensagem}"
        self.log_text.insert(tk.END, log_message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def limpar_log(self):
        """Limpar a caixa de logs"""
        self.log_text.delete(1.0, tk.END)
        self.adicionar_log("Log limpo pelo usuário")

    def copiar_log(self):
        """Copiar todo o conteúdo do log para a área de transferência"""
        try:
            log_content = self.log_text.get(1.0, tk.END)
            self.root.clipboard_clear()
            self.root.clipboard_append(log_content)
            self.adicionar_log("Log copiado para a área de transferência")
        except Exception as e:
            self.adicionar_log(f"Erro ao copiar log: {str(e)}")

    def parar_processamento(self):
        """Parar o processamento em lote"""
        self.processamento_ativo = False
        self.adicionar_log("🛑 PARADA SOLICITADA PELO USUÁRIO")

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

    def processar_lote_thread(self):
        """Executar processamento em lote em thread separada"""
        thread = threading.Thread(target=self.processar_lote)
        thread.daemon = True
        thread.start()

    def processar_lote(self):
        """Função principal para processar lote"""
        if not self.arquivos_selecionados:
            messagebox.showerror("Erro", "Nenhum arquivo selecionado.")
            return

        api_key = self.api_key_entry.get().strip()
        
        # Verificar se API key é necessária
        if not self.usar_apenas_local and not self.modo_privacidade and not api_key:
            messagebox.showerror("Erro", "API Key necessária para processamento na nuvem.")
            return

        self.processamento_ativo = True
        self.processar_button.config(state=tk.DISABLED, text="PROCESSANDO...")
        
        self.adicionar_log("=== INICIANDO PROCESSAMENTO HÍBRIDO ===")
        
        # Reset estatísticas
        self.stats_local = 0
        self.stats_cloud = 0
        self.stats_failed = 0
        self.atualizar_estatisticas()
        
        arquivos_processados = 0
        arquivos_com_sucesso = 0
        
        for i, arquivo in enumerate(self.arquivos_selecionados):
            if not self.processamento_ativo:
                self.adicionar_log("🛑 PROCESSAMENTO INTERROMPIDO")
                break
            
            nome_arquivo = os.path.basename(arquivo)
            self.adicionar_log(f"\n{'='*50}")
            self.adicionar_log(f"🔄 PROCESSANDO {i+1}/{len(self.arquivos_selecionados)}: {nome_arquivo}")
            
            # Atualizar progresso
            progresso = (i / len(self.arquivos_selecionados)) * 100
            self.progress_var.set(progresso)
            self.root.update_idletasks()
            
            try:
                # Processar com lógica híbrida
                resultado = self.processar_arquivo_hibrido(arquivo, api_key)
                
                if resultado:
                    # Salvar resultado
                    if self.salvar_resultados_melhorado(resultado, arquivo):
                        self.adicionar_log(f"✅ SUCESSO: {nome_arquivo}")
                        arquivos_com_sucesso += 1
                    else:
                        self.adicionar_log(f"⚠ OCR OK, mas falha ao salvar")
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
        
        if arquivos_com_sucesso > 0:
            messagebox.showinfo("Processamento Concluído", 
                               f"Lote processado!\n\n"
                               f"✅ Sucessos: {arquivos_com_sucesso}/{arquivos_processados}\n"
                               f"🏠 Local: {self.stats_local}\n"
                               f"☁️ Cloud: {self.stats_cloud}\n"
                               f"📁 Arquivos salvos em:\n{self.pasta_destino}")
        
        self.status_label.config(text=f"Concluído: {arquivos_com_sucesso}/{arquivos_processados} sucessos")
        self.processar_button.config(state=tk.NORMAL, text="PROCESSAR LOTE")
        self.processamento_ativo = False

    def salvar_resultados_melhorado(self, resultado, nome_arquivo_original):
        """Salvar resultados com informações de método de processamento"""
        try:
            nome_base = os.path.splitext(os.path.basename(nome_arquivo_original))[0]
            nome_base = nome_base.replace(" ", "_")

            os.makedirs(self.pasta_destino, exist_ok=True)

            # Adicionar informações de processamento aos metadados
            metadata = resultado.get("metadata", {})
            metadata["processed_at"] = datetime.datetime.now().isoformat()
            metadata["processing_mode"] = "hybrid" if not self.usar_apenas_local else "local_only"
            
            resultado["metadata"] = metadata

            # Salvar JSON
            json_filename = os.path.join(self.pasta_destino, f"{nome_base}_OCR_enhanced.json")
            with open(json_filename, "w", encoding="utf-8") as f:
                json.dump(resultado, f, indent=2, ensure_ascii=False)

            # Salvar Markdown melhorado
            pages = resultado.get("pages", [])
            if pages:
                md_filename = os.path.join(self.pasta_destino, f"{nome_base}_OCR.md")
                with open(md_filename, "w", encoding="utf-8") as f:
                    f.write(f"# Resultado OCR - {nome_base}\n\n")
                    f.write(f"**Data:** {time.strftime('%d/%m/%Y %H:%M:%S')}\n")
                    
                    # Informações de processamento
                    metodo = metadata.get("method", "unknown")
                    if metodo == "tesseract_local":
                        f.write(f"**Método:** 🏠 Processamento Local (Tesseract)\n")
                    elif metodo == "mistral_cloud":
                        f.write(f"**Método:** ☁️ Processamento na Nuvem (Mistral AI)\n")
                    else:
                        f.write(f"**Método:** {metodo}\n")
                    
                    if "average_confidence" in metadata:
                        f.write(f"**Confiança:** {metadata['average_confidence']:.2f}\n")
                    
                    f.write(f"**Total de páginas:** {len(pages)}\n\n")
                    
                    for i, page in enumerate(pages, 1):
                        text_content = page.get("text", "") or page.get("markdown", "")
                        confidence = page.get("confidence", 0)
                        
                        f.write(f"## Página {i}")
                        if confidence > 0:
                            f.write(f" (Confiança: {confidence:.2f})")
                        f.write("\n\n")
                        
                        f.write(text_content)
                        f.write("\n\n" + "="*60 + "\n\n")

            self.adicionar_log(f"💾 Resultados salvos: {nome_base}")
            return True

        except Exception as e:
            self.adicionar_log(f"✗ Erro ao salvar: {str(e)}")
            return False

    # === MÉTODOS ORIGINAIS PARA COMPATIBILIDADE ===
    
    def criar_sessao_robusta(self):
        """Criar sessão HTTP robusta (do código original)"""
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
        """Upload robusto (do código original - simplificado)"""
        try:
            session = self.criar_sessao_robusta()
            url = "https://api.mistral.ai/v1/files"
            headers = {"Authorization": f"Bearer {api_key}"}

            with open(caminho_arquivo, "rb") as f:
                files = {"file": f}
                data = {"purpose": "ocr"}
                response = session.post(url, headers=headers, files=files, data=data, timeout=60)

            if response.status_code == 200:
                return response.json()
            else:
                self.adicionar_log(f"❌ Upload falhou: {response.status_code}")
                return None

        except Exception as e:
            self.adicionar_log(f"❌ Erro no upload: {str(e)}")
            return None

    def processar_ocr_arquivo_robusto(self, file_id, api_key, nome_arquivo=None):
        """OCR robusto (do código original - simplificado)"""
        try:
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

            response = session.post(url, headers=headers, json=payload, timeout=300)

            if response.status_code == 200:
                result = response.json()
                # Adicionar metadata para compatibilidade
                if "metadata" not in result:
                    result["metadata"] = {"method": "mistral_cloud"}
                return result
            else:
                self.adicionar_log(f"❌ OCR falhou: {response.status_code}")
                return None

        except Exception as e:
            self.adicionar_log(f"❌ Erro no OCR: {str(e)}")
            return None

def main():
    root = tk.Tk()
    app = OCRBatchAppEnhanced(root)
    root.mainloop()

if __name__ == '__main__':
    main()