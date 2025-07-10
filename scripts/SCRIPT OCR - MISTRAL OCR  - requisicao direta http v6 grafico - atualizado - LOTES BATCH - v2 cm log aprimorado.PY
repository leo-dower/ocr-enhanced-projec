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

class OCRBatchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mistral OCR - Processamento em Lote Robusto")
        self.root.geometry("1400x800")
        self.root.resizable(True, True)

        # Configurações
        self.pasta_padrao = r"F:\OneDrive\Advocacia\ano_2025"  # Ajuste conforme necessário
        self.pasta_destino = r"F:\OneDrive\Advocacia\ano_2025"
        self.max_paginas_por_lote = 200
        self.arquivos_selecionados = []
        self.processamento_ativo = False
        self.max_tentativas = 3
        self.tempo_espera_base = 60

        # Criar interface
        self.criar_interface()

    def criar_interface(self):
        # Frame principal com layout de duas colunas
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Configurar colunas: esquerda (controles) e direita (log)
        main_frame.grid_columnconfigure(0, weight=2)  # Área principal (2/3)
        main_frame.grid_columnconfigure(1, weight=1)  # Área do log (1/3)
        main_frame.grid_rowconfigure(0, weight=1)

        # Frame esquerdo - Controles principais
        left_frame = tk.Frame(main_frame, relief="raised", bd=1)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_frame.grid_columnconfigure(1, weight=1)

        # Frame direito - Log
        right_frame = tk.Frame(main_frame, relief="raised", bd=1)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)

        # === ÁREA ESQUERDA - CONTROLES ===
        
        # Título
        titulo = tk.Label(left_frame, text="Mistral OCR - Processamento em Lote Robusto", 
                         font=("Arial", 14, "bold"), fg="darkblue")
        titulo.grid(row=0, column=0, columnspan=3, pady=10)

        # API Key
        tk.Label(left_frame, text="API Key:", font=("Arial", 10)).grid(
            row=1, column=0, sticky="e", padx=10, pady=8)
        self.api_key_entry = tk.Entry(left_frame, width=50, show="*", font=("Arial", 10))
        self.api_key_entry.grid(row=1, column=1, columnspan=2, padx=10, pady=8, sticky="ew")

        # Configurações robustas
        config_frame = tk.LabelFrame(left_frame, text="Configurações Robustas", font=("Arial", 10, "bold"))
        config_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=10)
        config_frame.grid_columnconfigure(1, weight=1)

        # Linha 1 - Páginas e tentativas
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

        # Linha 2 - Opções
        self.dividir_automatico = tk.BooleanVar(value=True)
        tk.Checkbutton(config_frame, text="Dividir automaticamente", 
                      variable=self.dividir_automatico, font=("Arial", 9)).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=5, pady=5)

        self.modo_conservador = tk.BooleanVar(value=False)
        tk.Checkbutton(config_frame, text="Modo conservador", 
                      variable=self.modo_conservador, font=("Arial", 9)).grid(
            row=1, column=2, columnspan=2, sticky="w", padx=5, pady=5)

        # Linha 3 - Log detalhado
        self.log_detalhado = tk.BooleanVar(value=True)
        tk.Checkbutton(config_frame, text="Log detalhado (diagnóstico)", 
                      variable=self.log_detalhado, font=("Arial", 9)).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=5, pady=5)

        # Status da API
        self.status_api_frame = tk.Frame(config_frame)
        self.status_api_frame.grid(row=3, column=0, columnspan=4, pady=5)
        
        self.status_api_label = tk.Label(self.status_api_frame, text="Status da API: Não verificado", 
                                        fg="gray", font=("Arial", 9))
        self.status_api_label.pack(side=tk.LEFT)
        
        self.verificar_api_button = tk.Button(self.status_api_frame, text="Verificar API", 
                                             command=self.verificar_status_api,
                                             bg="lightblue", font=("Arial", 8))
        self.verificar_api_button.pack(side=tk.LEFT, padx=10)

        # Seleção de arquivos
        arquivo_frame = tk.LabelFrame(left_frame, text="Seleção de Arquivos", font=("Arial", 10, "bold"))
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

        self.files_listbox = tk.Listbox(list_frame, height=8, font=("Arial", 9))
        self.files_listbox.grid(row=0, column=0, sticky="ew")

        scrollbar_files = tk.Scrollbar(list_frame, orient="vertical")
        scrollbar_files.grid(row=0, column=1, sticky="ns")
        self.files_listbox.config(yscrollcommand=scrollbar_files.set)
        scrollbar_files.config(command=self.files_listbox.yview)

        self.status_lote_label = tk.Label(arquivo_frame, text="Nenhum arquivo selecionado", 
                                         fg="gray", font=("Arial", 9))
        self.status_lote_label.grid(row=3, column=0, columnspan=3, pady=5)

        # Pasta de destino
        tk.Label(left_frame, text="Destino:", font=("Arial", 10)).grid(
            row=4, column=0, sticky="e", padx=10, pady=8)
        destino_label = tk.Label(left_frame, text=self.pasta_destino, 
                                font=("Arial", 9), fg="darkgreen", 
                                relief="sunken", anchor="w")
        destino_label.grid(row=4, column=1, columnspan=2, sticky="ew", padx=10, pady=8)

        # Barra de progresso
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(left_frame, variable=self.progress_var, 
                                           maximum=100, length=300)
        self.progress_bar.grid(row=5, column=0, columnspan=3, pady=10, sticky="ew", padx=10)

        # Botão processar
        self.processar_button = tk.Button(left_frame, text="PROCESSAR LOTE", 
                                         command=self.processar_lote_thread,
                                         bg="green", fg="white", 
                                         font=("Arial", 12, "bold"),
                                         height=2)
        self.processar_button.grid(row=6, column=0, columnspan=3, pady=15, padx=10)

        # Status
        self.status_label = tk.Label(left_frame, text="Pronto para processar...", 
                                    fg="blue", font=("Arial", 10))
        self.status_label.grid(row=7, column=0, columnspan=3, pady=5)

        # === ÁREA DIREITA - LOG ===
        
        # Título do log
        log_title = tk.Label(right_frame, text="Log de Execução", 
                            font=("Arial", 11, "bold"), fg="darkred")
        log_title.grid(row=0, column=0, sticky="w", pady=(5,0), padx=5)

        # Área de log
        self.log_text = scrolledtext.ScrolledText(right_frame, 
                                                 width=60, height=35,
                                                 font=("Consolas", 8),
                                                 bg="black", fg="lightgreen",
                                                 wrap=tk.WORD)
        self.log_text.grid(row=1, column=0, sticky="nsew", pady=5, padx=5)

        # Botões do log
        log_button_frame = tk.Frame(right_frame)
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

        # Log inicial
        self.adicionar_log("=== MISTRAL OCR LOTE ROBUSTO INICIADO ===")
        self.adicionar_log(f"Pasta padrão: {self.pasta_padrao}")
        self.adicionar_log(f"Pasta destino: {self.pasta_destino}")
        self.adicionar_log("💡 Dica: Verifique o status da API antes de processar")

    def adicionar_log_detalhado(self, mensagem, response=None, start_time=None, end_time=None, 
                               tentativa=None, arquivo=None, nivel="INFO"):
        """Adicionar log com informações detalhadas para diagnóstico"""
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
        # Construir mensagem base
        log_message = f"[{timestamp}] [{nivel}] {mensagem}"
        
        # Adicionar informações extras se disponíveis
        if tentativa is not None:
            log_message += f" (Tentativa {tentativa})"
        
        if arquivo is not None:
            nome_arquivo = os.path.basename(arquivo) if isinstance(arquivo, str) else str(arquivo)
            log_message += f" - Arquivo: {nome_arquivo}"
        
        if start_time and end_time:
            duracao = end_time - start_time
            log_message += f" - Duração: {duracao:.2f}s"
        
        # Informações da resposta HTTP
        if response is not None:
            log_message += f" - Status: {response.status_code}"
            
            if self.log_detalhado.get():
                # Headers importantes
                content_type = response.headers.get('content-type', 'N/A')
                content_length = response.headers.get('content-length', 'N/A')
                log_message += f" - Content-Type: {content_type}"
                log_message += f" - Content-Length: {content_length}"
                
                # Resposta (limitada)
                try:
                    if response.status_code != 200:
                        resposta_texto = response.text[:300] if response.text else "Sem conteúdo"
                        log_message += f" - Resposta: {resposta_texto}"
                except:
                    log_message += " - Resposta: [Erro ao ler]"
        
        # Adicionar ao log visual
        self.log_text.insert(tk.END, log_message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def adicionar_log(self, mensagem, nivel="INFO"):
        """Wrapper para compatibilidade com código existente"""
        self.adicionar_log_detalhado(mensagem, nivel=nivel)

    def log_info_sistema(self):
        """Logar informações do sistema para diagnóstico"""
        if not self.log_detalhado.get():
            return
            
        try:
            # Informações de rede
            hostname = socket.gethostname()
            ip_local = socket.gethostbyname(hostname)
            
            # Informações básicas do sistema
            sistema = platform.system()
            versao = platform.version()
            
            self.adicionar_log_detalhado(f"Sistema - Host: {hostname} - IP: {ip_local} - OS: {sistema} {versao}")
            
        except Exception as e:
            self.adicionar_log_detalhado(f"Erro ao coletar info do sistema: {str(e)}", nivel="WARNING")

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

    def verificar_status_api(self):
        """Verificar se a API está respondendo com logs detalhados"""
        api_key = self.api_key_entry.get().strip()
        if not api_key:
            self.status_api_label.config(text="Status da API: API Key necessária", fg="red")
            return

        def verificar():
            start_time = time.time()
            try:
                self.status_api_label.config(text="Status da API: Verificando...", fg="orange")
                self.root.update_idletasks()
                
                self.adicionar_log_detalhado("Iniciando verificação da API")
                
                session = self.criar_sessao_robusta()
                url = "https://api.mistral.ai/v1/models"
                headers = {"Authorization": f"Bearer {api_key}"}
                
                response = session.get(url, headers=headers, timeout=10)
                end_time = time.time()
                
                if response.status_code == 200:
                    self.status_api_label.config(text="Status da API: ✓ Online e funcionando", fg="green")
                    self.adicionar_log_detalhado("API verificada com sucesso", response=response, 
                                                start_time=start_time, end_time=end_time)
                else:
                    self.status_api_label.config(text=f"Status da API: ✗ Erro {response.status_code}", fg="red")
                    self.adicionar_log_detalhado("API com problemas", response=response, 
                                                start_time=start_time, end_time=end_time, nivel="ERROR")
                    
            except Exception as e:
                end_time = time.time()
                self.status_api_label.config(text="Status da API: ✗ Indisponível", fg="red")
                self.adicionar_log_detalhado(f"API indisponível: {str(e)}", 
                                           start_time=start_time, end_time=end_time, nivel="ERROR")
        
        thread = threading.Thread(target=verificar)
        thread.daemon = True
        thread.start()

    def verificar_horario_otimo(self):
        """Verificar se é um bom horário para processamento"""
        hora_atual = time.localtime().tm_hour
        
        # Horários com menor carga
        horarios_otimos = [2, 3, 4, 5, 6, 7, 8, 14, 15]
        
        if hora_atual not in horarios_otimos:
            self.adicionar_log(f"⚠ Horário atual ({hora_atual}h) pode ter alta demanda")
            self.adicionar_log("💡 Horários recomendados: 02h-08h ou 14h-16h")
            
            if not self.modo_conservador.get():
                resposta = messagebox.askyesno(
                    "Horário de Alta Demanda",
                    f"Horário atual ({hora_atual}h) pode ter alta demanda na API.\n\n"
                    "Horários recomendados: 02h-08h ou 14h-16h\n\n"
                    "Deseja continuar mesmo assim?"
                )
                return resposta
        
        return True

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
            'User-Agent': 'OCR-Batch-Client/2.0',
            'Connection': 'keep-alive',
            'Accept-Encoding': 'gzip, deflate',
            'Accept': 'application/json',
            'Cache-Control': 'no-cache'
        })
        
        return session

    def contar_paginas_pdf(self, caminho_arquivo):
        """Contar páginas com tratamento de erro melhorado"""
        try:
            with open(caminho_arquivo, 'rb') as arquivo:
                leitor = PyPDF2.PdfReader(arquivo)
                return len(leitor.pages)
        except Exception as e:
            self.adicionar_log(f"⚠ Erro ao contar páginas de {os.path.basename(caminho_arquivo)}: {str(e)}")
            try:
                tamanho_mb = os.path.getsize(caminho_arquivo) / (1024 * 1024)
                paginas_estimadas = int(tamanho_mb * 10)
                self.adicionar_log(f"📊 Estimativa baseada no tamanho: {paginas_estimadas} páginas")
                return paginas_estimadas
            except:
                return 0

    def evitar_divisao_dupla(self, caminho_arquivo):
        """Verificar se arquivo já foi dividido para evitar divisão dupla"""
        nome_arquivo = os.path.basename(caminho_arquivo)
        
        if "_parte_" in nome_arquivo:
            self.adicionar_log(f"📄 Arquivo já dividido detectado: {nome_arquivo}")
            return False
        
        return True

    def dividir_pdf(self, caminho_arquivo, max_paginas):
        """Dividir PDF com verificação de divisão dupla"""
        try:
            if not self.evitar_divisao_dupla(caminho_arquivo):
                return [caminho_arquivo]
            
            self.adicionar_log(f"📄 Analisando PDF: {os.path.basename(caminho_arquivo)}")
            
            with open(caminho_arquivo, 'rb') as arquivo:
                leitor = PyPDF2.PdfReader(arquivo)
                total_paginas = len(leitor.pages)
                
                if total_paginas <= max_paginas:
                    self.adicionar_log(f"✓ Arquivo dentro do limite ({total_paginas} páginas)")
                    return [caminho_arquivo]
                
                num_partes = math.ceil(total_paginas / max_paginas)
                self.adicionar_log(f"✂️ Dividindo em {num_partes} partes ({total_paginas} páginas)")
                
                partes = []
                nome_base = os.path.splitext(caminho_arquivo)[0]
                
                for i in range(num_partes):
                    escritor = PyPDF2.PdfWriter()
                    inicio = i * max_paginas
                    fim = min((i + 1) * max_paginas, total_paginas)
                    
                    for j in range(inicio, fim):
                        escritor.add_page(leitor.pages[j])
                    
                    nome_parte = f"{nome_base}_subdiv_{i+1:02d}.pdf"
                    with open(nome_parte, 'wb') as arquivo_saida:
                        escritor.write(arquivo_saida)
                    
                    partes.append(nome_parte)
                    self.adicionar_log(f"  ✓ Criada subdivisão {i+1}: {fim-inicio} páginas")
                
                return partes
                
        except Exception as e:
            self.adicionar_log(f"✗ Erro ao dividir PDF {os.path.basename(caminho_arquivo)}: {str(e)}")
            return [caminho_arquivo]

    def upload_arquivo_robusto(self, caminho_arquivo, api_key):
        """Upload com logs detalhados"""
        max_tentativas = int(self.max_tentativas_entry.get())
        nome_arquivo = os.path.basename(caminho_arquivo)
        
        try:
            tamanho_mb = os.path.getsize(caminho_arquivo) / (1024 * 1024)
            self.adicionar_log_detalhado(f"Iniciando upload - Tamanho: {tamanho_mb:.2f}MB", arquivo=nome_arquivo)
        except:
            pass
        
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

            except requests.exceptions.ConnectionError as e:
                end_time = time.time()
                if "10054" in str(e):
                    self.adicionar_log_detalhado(f"Conexão resetada pelo servidor (erro 10054)", 
                                               start_time=start_time, end_time=end_time,
                                               tentativa=tentativa+1, arquivo=nome_arquivo, nivel="WARNING")
                    if tentativa < max_tentativas - 1:
                        continue
                else:
                    self.adicionar_log_detalhado(f"Erro de conexão: {str(e)}", 
                                               start_time=start_time, end_time=end_time,
                                               tentativa=tentativa+1, arquivo=nome_arquivo, nivel="ERROR")
                    return None
            except Exception as e:
                end_time = time.time()
                self.adicionar_log_detalhado(f"Erro inesperado no upload: {str(e)}", 
                                           start_time=start_time, end_time=end_time,
                                           tentativa=tentativa+1, arquivo=nome_arquivo, nivel="ERROR")
                if tentativa < max_tentativas - 1:
                    continue
                return None
        
        self.adicionar_log_detalhado(f"Upload falhou após {max_tentativas} tentativas", 
                                   arquivo=nome_arquivo, nivel="ERROR")
        return None

    def processar_ocr_arquivo_robusto(self, file_id, api_key, nome_arquivo=None):
        """OCR com logs detalhados"""
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
                    try:
                        result = response.json()
                        num_paginas = len(result.get("pages", []))
                        self.adicionar_log_detalhado(f"OCR concluído - {num_paginas} páginas processadas", 
                                                   response=response, start_time=start_time, end_time=end_time,
                                                   tentativa=tentativa+1, arquivo=nome_arquivo)
                    except:
                        self.adicionar_log_detalhado("OCR concluído", response=response,
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
                    
            except requests.exceptions.Timeout:
                end_time = time.time()
                self.adicionar_log_detalhado(f"Timeout após {timeout_atual}s - Documento muito complexo", 
                                           start_time=start_time, end_time=end_time,
                                           tentativa=tentativa+1, arquivo=nome_arquivo, nivel="WARNING")
                if tentativa < max_tentativas - 1:
                    continue
            except requests.exceptions.ConnectionError as e:
                end_time = time.time()
                if "10054" in str(e):
                    self.adicionar_log_detalhado("Conexão resetada pelo servidor (erro 10054)", 
                                               start_time=start_time, end_time=end_time,
                                               tentativa=tentativa+1, arquivo=nome_arquivo, nivel="WARNING")
                    if tentativa < max_tentativas - 1:
                        continue
                else:
                    self.adicionar_log_detalhado(f"Erro de conexão: {str(e)}", 
                                               start_time=start_time, end_time=end_time,
                                               tentativa=tentativa+1, arquivo=nome_arquivo, nivel="ERROR")
                    return None
            except Exception as e:
                end_time = time.time()
                self.adicionar_log_detalhado(f"Erro inesperado no OCR: {str(e)}", 
                                           start_time=start_time, end_time=end_time,
                                           tentativa=tentativa+1, arquivo=nome_arquivo, nivel="ERROR")
                if tentativa < max_tentativas - 1:
                    continue
                return None
        
        self.adicionar_log_detalhado(f"OCR falhou após {max_tentativas} tentativas", 
                                   arquivo=nome_arquivo, nivel="ERROR")
        return None

    def salvar_resultados(self, ocr_result, nome_arquivo_original, parte_numero=None):
        """Salvar resultados na pasta de destino"""
        try:
            nome_base = os.path.splitext(os.path.basename(nome_arquivo_original))[0]
            nome_base = nome_base.replace(" ", "_")
            
            if parte_numero:
                nome_base = f"{nome_base}_subdiv_{parte_numero:02d}"

            os.makedirs(self.pasta_destino, exist_ok=True)

            # Salvar JSON
            json_filename = os.path.join(self.pasta_destino, f"{nome_base}_OCR_completo.json")
            with open(json_filename, "w", encoding="utf-8") as f:
                json.dump(ocr_result, f, indent=2, ensure_ascii=False)

            # Salvar Markdown
            pages = ocr_result.get("pages", [])
            if pages:
                md_filename = os.path.join(self.pasta_destino, f"{nome_base}_OCR.md")
                with open(md_filename, "w", encoding="utf-8") as f:
                    f.write(f"# Resultado OCR - {nome_base}\n")
                    f.write(f"**Data:** {time.strftime('%d/%m/%Y %H:%M:%S')}\n\n")
                    
                    for i, page in enumerate(pages, 1):
                        markdown_content = page.get("markdown", "")
                        if markdown_content:
                            f.write(f"## Página {i}\n\n")
                            f.write(markdown_content)
                            f.write("\n\n" + "="*60 + "\n\n")

            self.adicionar_log(f"💾 Resultados salvos: {nome_base}")
            return True

        except Exception as e:
            self.adicionar_log(f"✗ Erro ao salvar: {str(e)}")
            return False

    def exportar_log(self):
        """Exportar log detalhado para arquivo"""
        try:
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Arquivos de texto", "*.txt"), ("Todos os arquivos", "*.*")],
                initialname=f"ocr_log_detalhado_{timestamp}.txt"
            )
            
            if filename:
                log_content = self.log_text.get(1.0, tk.END)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"=== LOG DETALHADO MISTRAL OCR ===\n")
                    f.write(f"Exportado em: {datetime.datetime.now()}\n")
                    f.write(f"Versão: Processamento em Lote Robusto\n")
                    f.write("="*50 + "\n\n")
                    f.write(log_content)
                
                self.adicionar_log_detalhado(f"Log exportado para: {filename}")
                messagebox.showinfo("Exportação", f"Log exportado com sucesso para:\n{filename}")
        except Exception as e:
            self.adicionar_log_detalhado(f"Erro ao exportar log: {str(e)}", nivel="ERROR")

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

    def atualizar_progresso(self, atual, total):
        """Atualizar barra de progresso"""
        if total > 0:
            progresso = (atual / total) * 100
            self.progress_var.set(progresso)
            self.root.update_idletasks()

    def processar_lote_thread(self):
        """Executar processamento em lote em thread separada"""
        thread = threading.Thread(target=self.processar_lote)
        thread.daemon = True
        thread.start()

    def processar_lote(self):
        """Função principal para processar lote com todas as melhorias"""
        if not self.arquivos_selecionados:
            messagebox.showerror("Erro", "Nenhum arquivo selecionado.")
            return

        api_key = self.api_key_entry.get().strip()
        if not api_key:
            messagebox.showerror("Erro", "Por favor, insira a API Key.")
            return

        # Log informações do sistema
        self.log_info_sistema()

        # Verificar horário se não estiver no modo conservador
        if not self.verificar_horario_otimo():
            return

        try:
            self.max_paginas_por_lote = int(self.max_paginas_entry.get())
            self.max_tentativas = int(self.max_tentativas_entry.get())
        except ValueError:
            self.max_paginas_por_lote = 200
            self.max_tentativas = 3

        self.processamento_ativo = True
        self.processar_button.config(state=tk.DISABLED, text="PROCESSANDO...")
        
        self.adicionar_log_detalhado("=== INICIANDO PROCESSAMENTO ROBUSTO ===")
        self.adicionar_log_detalhado(f"Total de arquivos: {len(self.arquivos_selecionados)}")
        self.adicionar_log_detalhado(f"Máximo de páginas por lote: {self.max_paginas_por_lote}")
        self.adicionar_log_detalhado(f"Máximo de tentativas: {self.max_tentativas}")
        self.adicionar_log_detalhado(f"Modo conservador: {'Ativado' if self.modo_conservador.get() else 'Desativado'}")
        self.adicionar_log_detalhado(f"Log detalhado: {'Ativado' if self.log_detalhado.get() else 'Desativado'}")
        
        arquivos_processados = 0
        arquivos_com_sucesso = 0
        total_arquivos = 0
        
        # Preparar lista de arquivos para processamento
        arquivos_para_processar = []
        
        for arquivo_original in self.arquivos_selecionados:
            if not self.processamento_ativo:
                break
                
            if not os.path.exists(arquivo_original):
                self.adicionar_log(f"✗ Arquivo não encontrado: {os.path.basename(arquivo_original)}")
                continue
            
            # Verificar se precisa dividir (evitando divisão dupla)
            if self.dividir_automatico.get():
                num_paginas = self.contar_paginas_pdf(arquivo_original)
                self.adicionar_log(f"📄 {os.path.basename(arquivo_original)} - {num_paginas} páginas")
                
                if num_paginas > self.max_paginas_por_lote and self.evitar_divisao_dupla(arquivo_original):
                    partes = self.dividir_pdf(arquivo_original, self.max_paginas_por_lote)
                    for parte in partes:
                        arquivos_para_processar.append((parte, arquivo_original, True))
                else:
                    arquivos_para_processar.append((arquivo_original, arquivo_original, False))
            else:
                arquivos_para_processar.append((arquivo_original, arquivo_original, False))
        
        total_arquivos = len(arquivos_para_processar)
        self.adicionar_log(f"📋 Total de arquivos/partes para processar: {total_arquivos}")
        
        # Processar cada arquivo/parte
        for i, (arquivo_para_processar, arquivo_original, eh_parte) in enumerate(arquivos_para_processar):
            if not self.processamento_ativo:
                self.adicionar_log("🛑 PROCESSAMENTO INTERROMPIDO")
                break
            
            self.atualizar_progresso(i, total_arquivos)
            nome_arquivo = os.path.basename(arquivo_para_processar)
            
            self.adicionar_log(f"\n{'='*60}")
            self.adicionar_log(f"🔄 PROCESSANDO {i+1}/{total_arquivos}: {nome_arquivo}")
            self.status_label.config(text=f"Processando {i+1}/{total_arquivos}: {nome_arquivo}")
            
            try:
                # Upload robusto
                upload_result = self.upload_arquivo_robusto(arquivo_para_processar, api_key)
                
                if not upload_result:
                    self.adicionar_log(f"✗ Falha definitiva no upload")
                    continue
                
                file_id = upload_result.get("id")
                if not file_id:
                    self.adicionar_log(f"✗ ID do arquivo não encontrado")
                    continue
                
                # OCR robusto
                ocr_result = self.processar_ocr_arquivo_robusto(file_id, api_key, nome_arquivo)
                
                if not ocr_result:
                    self.adicionar_log(f"✗ Falha definitiva no OCR")
                    continue
                
                # Salvar
                parte_numero = None
                if eh_parte and "_subdiv_" in nome_arquivo:
                    try:
                        parte_numero = int(nome_arquivo.split("_subdiv_")[1].split(".")[0])
                    except:
                        pass
                
                if self.salvar_resultados(ocr_result, arquivo_original, parte_numero):
                    self.adicionar_log(f"✅ SUCESSO COMPLETO: {nome_arquivo}")
                    arquivos_com_sucesso += 1
                else:
                    self.adicionar_log(f"⚠ OCR OK, mas falha ao salvar")
                
                # Limpar arquivo temporário
                if eh_parte and arquivo_para_processar != arquivo_original:
                    try:
                        os.remove(arquivo_para_processar)
                        self.adicionar_log(f"🗑️ Arquivo temporário removido")
                    except:
                        pass
                        
            except Exception as e:
                self.adicionar_log(f"💥 Erro inesperado: {str(e)}")
            
            arquivos_processados += 1
            
            # Pausa entre arquivos no modo conservador
            if self.modo_conservador.get() and i < total_arquivos - 1:
                pausa = random.randint(30, 60)
                self.adicionar_log(f"⏸️ Pausa conservadora: {pausa}s")
                time.sleep(pausa)
        
        # Finalizar
        self.atualizar_progresso(total_arquivos, total_arquivos)
        
        self.adicionar_log(f"\n{'='*60}")
        self.adicionar_log("🏁 PROCESSAMENTO CONCLUÍDO")
        self.adicionar_log(f"📊 Processados: {arquivos_processados}/{total_arquivos}")
        self.adicionar_log(f"✅ Sucessos: {arquivos_com_sucesso}")
        self.adicionar_log(f"❌ Falhas: {arquivos_processados - arquivos_com_sucesso}")
        
        if arquivos_com_sucesso > 0:
            messagebox.showinfo("Processamento Concluído", 
                               f"Lote processado com sucesso!\n\n"
                               f"✅ Sucessos: {arquivos_com_sucesso}/{arquivos_processados}\n"
                               f"📁 Arquivos salvos em:\n{self.pasta_destino}")
        else:
            messagebox.showerror("Processamento Falhou", 
                               f"Nenhum arquivo foi processado com sucesso.\n\n"
                               f"Verifique:\n"
                               f"• Status da API\n"
                               f"• Conexão com internet\n"
                               f"• Horário de processamento\n"
                               f"• Tamanho dos arquivos")
        
        self.status_label.config(text=f"Concluído: {arquivos_com_sucesso}/{arquivos_processados} sucessos")
        self.processar_button.config(state=tk.NORMAL, text="PROCESSAR LOTE")
        self.processamento_ativo = False

def main():
    root = tk.Tk()
    app = OCRBatchApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()
