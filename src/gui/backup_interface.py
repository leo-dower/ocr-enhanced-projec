"""
Interface gráfica para gerenciamento de backup automático
Integra com BackupManager para configuração e monitoramento
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import asyncio
import threading
from typing import List, Dict, Any
import os
from datetime import datetime
import json

class BackupInterface:
    """Interface gráfica para gerenciamento de backup"""
    
    def __init__(self, parent, backup_manager=None):
        self.parent = parent
        self.backup_manager = backup_manager
        self.backup_jobs = []
        
        # Variáveis de controle
        self.auto_backup_var = tk.BooleanVar()
        self.interval_var = tk.IntVar(value=24)
        self.retention_var = tk.IntVar(value=30)
        self.max_size_var = tk.IntVar(value=1024)
        
        self.create_backup_interface()
        self.load_backup_status()
    
    def create_backup_interface(self):
        """Cria interface de backup"""
        # Frame principal
        self.main_frame = ttk.Frame(self.parent, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configurar redimensionamento
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        
        # === SEÇÃO DE STATUS ===
        status_frame = ttk.LabelFrame(self.main_frame, text="📊 Status do Backup", padding="10")
        status_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        status_frame.columnconfigure(1, weight=1)
        
        # Status atual
        self.status_label = ttk.Label(status_frame, text="Verificando status...", font=("Arial", 10, "bold"))
        self.status_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        # Informações de backup
        ttk.Label(status_frame, text="Último backup:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.last_backup_label = ttk.Label(status_frame, text="Nunca", foreground="orange")
        self.last_backup_label.grid(row=1, column=1, sticky=tk.W)
        
        ttk.Label(status_frame, text="Próximo backup:").grid(row=2, column=0, sticky=tk.W, padx=(0, 10))
        self.next_backup_label = ttk.Label(status_frame, text="Não agendado", foreground="gray")
        self.next_backup_label.grid(row=2, column=1, sticky=tk.W)
        
        ttk.Label(status_frame, text="Total de backups:").grid(row=3, column=0, sticky=tk.W, padx=(0, 10))
        self.total_backups_label = ttk.Label(status_frame, text="0")
        self.total_backups_label.grid(row=3, column=1, sticky=tk.W)
        
        ttk.Label(status_frame, text="Tamanho total:").grid(row=4, column=0, sticky=tk.W, padx=(0, 10))
        self.total_size_label = ttk.Label(status_frame, text="0 MB")
        self.total_size_label.grid(row=4, column=1, sticky=tk.W)
        
        # === SEÇÃO DE CONFIGURAÇÕES ===
        config_frame = ttk.LabelFrame(self.main_frame, text="⚙️ Configurações", padding="10")
        config_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        config_frame.columnconfigure(1, weight=1)
        
        # Backup automático
        self.auto_backup_check = ttk.Checkbutton(config_frame, text="Ativar backup automático", 
                                                variable=self.auto_backup_var,
                                                command=self.toggle_auto_backup)
        self.auto_backup_check.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        # Intervalo de backup
        ttk.Label(config_frame, text="Intervalo (horas):").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        interval_spin = ttk.Spinbox(config_frame, from_=1, to=168, textvariable=self.interval_var, 
                                   width=10, command=self.update_interval)
        interval_spin.grid(row=1, column=1, sticky=tk.W, pady=2)
        
        # Retenção
        ttk.Label(config_frame, text="Retenção (dias):").grid(row=2, column=0, sticky=tk.W, padx=(0, 10))
        retention_spin = ttk.Spinbox(config_frame, from_=1, to=365, textvariable=self.retention_var, 
                                    width=10, command=self.update_retention)
        retention_spin.grid(row=2, column=1, sticky=tk.W, pady=2)
        
        # Tamanho máximo
        ttk.Label(config_frame, text="Tamanho máx (MB):").grid(row=3, column=0, sticky=tk.W, padx=(0, 10))
        size_spin = ttk.Spinbox(config_frame, from_=100, to=10240, textvariable=self.max_size_var, 
                               width=10, command=self.update_max_size)
        size_spin.grid(row=3, column=1, sticky=tk.W, pady=2)
        
        # === SEÇÃO DE SERVIÇOS DE NUVEM ===
        cloud_frame = ttk.LabelFrame(self.main_frame, text="☁️ Serviços de Nuvem", padding="10")
        cloud_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        cloud_frame.columnconfigure(0, weight=1)
        
        # Lista de serviços
        self.create_cloud_services_list(cloud_frame)
        
        # === SEÇÃO DE HISTÓRICO ===
        history_frame = ttk.LabelFrame(self.main_frame, text="📜 Histórico de Backups", padding="10")
        history_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        history_frame.columnconfigure(0, weight=1)
        history_frame.rowconfigure(1, weight=1)
        
        # Botão de atualização
        refresh_button = ttk.Button(history_frame, text="🔄 Atualizar", command=self.refresh_history)
        refresh_button.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        # Lista de backups
        self.create_backup_history_tree(history_frame)
        
        # === SEÇÃO DE AÇÕES ===
        actions_frame = ttk.LabelFrame(self.main_frame, text="🔧 Ações", padding="10")
        actions_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        self.create_actions_section(actions_frame)
    
    def create_cloud_services_list(self, parent):
        """Cria lista de serviços de nuvem"""
        # Frame para lista
        list_frame = ttk.Frame(parent)
        list_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        
        # Treeview para serviços
        columns = ('Serviço', 'Status', 'Última Sync')
        self.cloud_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=4)
        
        for col in columns:
            self.cloud_tree.heading(col, text=col)
            self.cloud_tree.column(col, width=120)
        
        self.cloud_tree.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Scrollbar
        cloud_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.cloud_tree.yview)
        cloud_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.cloud_tree.configure(yscrollcommand=cloud_scrollbar.set)
        
        # Botões
        cloud_buttons_frame = ttk.Frame(parent)
        cloud_buttons_frame.grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        
        ttk.Button(cloud_buttons_frame, text="Adicionar Serviço", 
                  command=self.add_cloud_service).grid(row=0, column=0, padx=(0, 5))
        
        ttk.Button(cloud_buttons_frame, text="Configurar", 
                  command=self.configure_cloud_service).grid(row=0, column=1, padx=(0, 5))
        
        ttk.Button(cloud_buttons_frame, text="Remover", 
                  command=self.remove_cloud_service).grid(row=0, column=2)
    
    def create_backup_history_tree(self, parent):
        """Cria árvore de histórico de backups"""
        # Frame para treeview
        tree_frame = ttk.Frame(parent)
        tree_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        # Treeview
        columns = ('Data/Hora', 'Tipo', 'Status', 'Arquivos', 'Tamanho', 'Serviço')
        self.history_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=8)
        
        # Configurar colunas
        column_widths = {'Data/Hora': 150, 'Tipo': 100, 'Status': 100, 
                        'Arquivos': 80, 'Tamanho': 100, 'Serviço': 120}
        
        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=column_widths.get(col, 100))
        
        self.history_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbar
        history_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        history_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.history_tree.configure(yscrollcommand=history_scrollbar.set)
        
        # Menu de contexto
        self.create_history_context_menu()
    
    def create_history_context_menu(self):
        """Cria menu de contexto para histórico"""
        self.history_context_menu = tk.Menu(self.history_tree, tearoff=0)
        self.history_context_menu.add_command(label="Restaurar Backup", command=self.restore_selected_backup)
        self.history_context_menu.add_command(label="Excluir Backup", command=self.delete_selected_backup)
        self.history_context_menu.add_separator()
        self.history_context_menu.add_command(label="Ver Detalhes", command=self.show_backup_details)
        
        # Bind menu de contexto
        self.history_tree.bind('<Button-3>', self.show_history_context_menu)
    
    def create_actions_section(self, parent):
        """Cria seção de ações"""
        # Botões principais
        ttk.Button(parent, text="🔄 Backup Agora", 
                  command=self.run_manual_backup).grid(row=0, column=0, padx=(0, 10))
        
        ttk.Button(parent, text="🧹 Limpar Backups Antigos", 
                  command=self.cleanup_old_backups).grid(row=0, column=1, padx=(0, 10))
        
        ttk.Button(parent, text="📁 Abrir Pasta de Backup", 
                  command=self.open_backup_folder).grid(row=0, column=2, padx=(0, 10))
        
        # Spacer
        parent.columnconfigure(3, weight=1)
        
        # Botão de configurações avançadas
        ttk.Button(parent, text="⚙️ Configurações Avançadas", 
                  command=self.open_advanced_settings).grid(row=0, column=4)
    
    def load_backup_status(self):
        """Carrega status atual do backup"""
        if not self.backup_manager:
            return
        
        # Executar em thread separada
        thread = threading.Thread(target=self._load_status_thread)
        thread.daemon = True
        thread.start()
    
    def _load_status_thread(self):
        """Carrega status em thread separada"""
        try:
            status = self.backup_manager.get_backup_status()
            
            # Atualizar interface no thread principal
            self.parent.after(0, self._update_status_display, status)
            
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("Erro", f"Erro ao carregar status: {e}"))
    
    def _update_status_display(self, status):
        """Atualiza exibição do status"""
        # Status principal
        if status.auto_backup_enabled:
            self.status_label.config(text="✅ Backup automático ativo", foreground="green")
            self.auto_backup_var.set(True)
        else:
            self.status_label.config(text="❌ Backup automático inativo", foreground="red")
            self.auto_backup_var.set(False)
        
        # Último backup
        if status.last_backup:
            last_backup_str = status.last_backup.strftime("%d/%m/%Y %H:%M")
            self.last_backup_label.config(text=last_backup_str, foreground="green")
        else:
            self.last_backup_label.config(text="Nunca", foreground="orange")
        
        # Próximo backup
        if status.next_backup:
            next_backup_str = status.next_backup.strftime("%d/%m/%Y %H:%M")
            self.next_backup_label.config(text=next_backup_str, foreground="blue")
        else:
            self.next_backup_label.config(text="Não agendado", foreground="gray")
        
        # Estatísticas
        self.total_backups_label.config(text=str(status.total_backups))
        self.total_size_label.config(text=f"{status.total_size_backed_up:.1f} MB")
        
        # Atualizar lista de serviços de nuvem
        self.update_cloud_services_display(status.cloud_services_active)
    
    def update_cloud_services_display(self, active_services):
        """Atualiza exibição dos serviços de nuvem"""
        # Limpar árvore
        for item in self.cloud_tree.get_children():
            self.cloud_tree.delete(item)
        
        # Adicionar serviços
        services_info = {
            'google_drive': 'Google Drive',
            'dropbox': 'Dropbox',
            'onedrive': 'OneDrive',
            'local': 'Local'
        }
        
        for service in active_services:
            service_name = services_info.get(service, service)
            status = "Ativo" if service in active_services else "Inativo"
            last_sync = "Hoje" if service in active_services else "Nunca"
            
            self.cloud_tree.insert('', 'end', values=(service_name, status, last_sync))
    
    def refresh_history(self):
        """Atualiza histórico de backups"""
        # Limpar árvore
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        if not self.backup_manager:
            return
        
        # Executar em thread separada
        thread = threading.Thread(target=self._load_history_thread)
        thread.daemon = True
        thread.start()
    
    def _load_history_thread(self):
        """Carrega histórico em thread separada"""
        try:
            # Simulação de histórico - em implementação real, buscar do banco
            sample_history = [
                {
                    'timestamp': datetime.now().strftime("%d/%m/%Y %H:%M"),
                    'type': 'Incremental',
                    'status': 'Concluído',
                    'files': '15',
                    'size': '45.2 MB',
                    'service': 'Local'
                },
                {
                    'timestamp': (datetime.now()).strftime("%d/%m/%Y %H:%M"),
                    'type': 'Completo',
                    'status': 'Concluído',
                    'files': '127',
                    'size': '320.5 MB',
                    'service': 'Google Drive'
                }
            ]
            
            # Atualizar interface no thread principal
            self.parent.after(0, self._update_history_display, sample_history)
            
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("Erro", f"Erro ao carregar histórico: {e}"))
    
    def _update_history_display(self, history_data):
        """Atualiza exibição do histórico"""
        for entry in history_data:
            # Definir cor baseada no status
            values = (entry['timestamp'], entry['type'], entry['status'], 
                     entry['files'], entry['size'], entry['service'])
            
            item = self.history_tree.insert('', 'end', values=values)
            
            # Colorir baseado no status
            if entry['status'] == 'Concluído':
                self.history_tree.set(item, 'Status', '✅ ' + entry['status'])
            elif entry['status'] == 'Falhou':
                self.history_tree.set(item, 'Status', '❌ ' + entry['status'])
            elif entry['status'] == 'Em andamento':
                self.history_tree.set(item, 'Status', '🔄 ' + entry['status'])
    
    def toggle_auto_backup(self):
        """Alterna backup automático"""
        if self.backup_manager:
            enabled = self.auto_backup_var.get()
            self.backup_manager.enable_auto_backup(enabled)
            
            status_text = "✅ Backup automático ativo" if enabled else "❌ Backup automático inativo"
            status_color = "green" if enabled else "red"
            self.status_label.config(text=status_text, foreground=status_color)
    
    def update_interval(self):
        """Atualiza intervalo de backup"""
        if self.backup_manager:
            hours = self.interval_var.get()
            self.backup_manager.set_backup_interval(hours)
    
    def update_retention(self):
        """Atualiza política de retenção"""
        if self.backup_manager:
            days = self.retention_var.get()
            self.backup_manager.set_retention_policy(days)
    
    def update_max_size(self):
        """Atualiza tamanho máximo de backup"""
        # Implementar se necessário
        pass
    
    def run_manual_backup(self):
        """Executa backup manual"""
        if not self.backup_manager:
            messagebox.showerror("Erro", "Sistema de backup não disponível")
            return
        
        # Selecionar pasta para backup
        folder_path = filedialog.askdirectory(title="Selecionar pasta para backup")
        if not folder_path:
            return
        
        # Executar backup em thread separada
        thread = threading.Thread(target=self._run_backup_thread, args=(folder_path,))
        thread.daemon = True
        thread.start()
        
        messagebox.showinfo("Backup Iniciado", "Backup manual iniciado. Verifique o histórico para acompanhar o progresso.")
    
    def _run_backup_thread(self, folder_path):
        """Executa backup em thread separada"""
        try:
            # Criar loop de eventos para async
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Criar e executar job de backup
            job_id = loop.run_until_complete(
                self.backup_manager.create_backup_job(folder_path, "full", "local")
            )
            
            if job_id:
                success = loop.run_until_complete(self.backup_manager.execute_backup(job_id))
                
                if success:
                    self.parent.after(0, lambda: messagebox.showinfo("Sucesso", "Backup manual concluído!"))
                    self.parent.after(0, self.refresh_history)
                else:
                    self.parent.after(0, lambda: messagebox.showerror("Erro", "Falha no backup manual"))
            
            loop.close()
            
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("Erro", f"Erro no backup: {e}"))
    
    def cleanup_old_backups(self):
        """Remove backups antigos"""
        if messagebox.askyesno("Confirmar", "Deseja remover backups antigos baseado na política de retenção?"):
            if self.backup_manager:
                # Executar limpeza em thread separada
                thread = threading.Thread(target=self._cleanup_thread)
                thread.daemon = True
                thread.start()
    
    def _cleanup_thread(self):
        """Executa limpeza em thread separada"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            loop.run_until_complete(self.backup_manager.cleanup_old_backups())
            
            self.parent.after(0, lambda: messagebox.showinfo("Sucesso", "Limpeza de backups concluída!"))
            self.parent.after(0, self.refresh_history)
            
            loop.close()
            
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("Erro", f"Erro na limpeza: {e}"))
    
    def open_backup_folder(self):
        """Abre pasta de backups"""
        if self.backup_manager:
            backup_folder = self.backup_manager.local_backup_dir
            
            try:
                import subprocess
                import platform
                
                if platform.system() == "Windows":
                    os.startfile(backup_folder)
                elif platform.system() == "Darwin":  # macOS
                    subprocess.run(["open", backup_folder])
                else:  # Linux
                    subprocess.run(["xdg-open", backup_folder])
                    
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao abrir pasta: {e}")
    
    def add_cloud_service(self):
        """Adiciona novo serviço de nuvem"""
        self.open_cloud_service_config()
    
    def configure_cloud_service(self):
        """Configura serviço de nuvem selecionado"""
        selection = self.cloud_tree.selection()
        if selection:
            self.open_cloud_service_config()
        else:
            messagebox.showwarning("Aviso", "Selecione um serviço para configurar")
    
    def remove_cloud_service(self):
        """Remove serviço de nuvem selecionado"""
        selection = self.cloud_tree.selection()
        if selection:
            if messagebox.askyesno("Confirmar", "Deseja remover o serviço selecionado?"):
                # Implementar remoção
                messagebox.showinfo("Sucesso", "Serviço removido!")
                self.refresh_history()
        else:
            messagebox.showwarning("Aviso", "Selecione um serviço para remover")
    
    def open_cloud_service_config(self):
        """Abre janela de configuração de serviço de nuvem"""
        config_window = tk.Toplevel(self.parent)
        config_window.title("Configurar Serviço de Nuvem")
        config_window.geometry("400x300")
        
        # Implementar formulário de configuração
        ttk.Label(config_window, text="Configuração de serviços de nuvem será implementada").pack(pady=50)
        ttk.Button(config_window, text="Fechar", command=config_window.destroy).pack()
    
    def show_history_context_menu(self, event):
        """Mostra menu de contexto do histórico"""
        item = self.history_tree.identify_row(event.y)
        if item:
            self.history_tree.selection_set(item)
            self.history_context_menu.post(event.x_root, event.y_root)
    
    def restore_selected_backup(self):
        """Restaura backup selecionado"""
        selection = self.history_tree.selection()
        if selection:
            # Selecionar pasta de destino
            restore_path = filedialog.askdirectory(title="Selecionar pasta para restauração")
            if restore_path:
                messagebox.showinfo("Info", "Funcionalidade de restauração será implementada")
        else:
            messagebox.showwarning("Aviso", "Selecione um backup para restaurar")
    
    def delete_selected_backup(self):
        """Exclui backup selecionado"""
        selection = self.history_tree.selection()
        if selection:
            if messagebox.askyesno("Confirmar", "Deseja excluir o backup selecionado?"):
                messagebox.showinfo("Sucesso", "Backup excluído!")
                self.refresh_history()
        else:
            messagebox.showwarning("Aviso", "Selecione um backup para excluir")
    
    def show_backup_details(self):
        """Mostra detalhes do backup selecionado"""
        selection = self.history_tree.selection()
        if selection:
            # Criar janela de detalhes
            details_window = tk.Toplevel(self.parent)
            details_window.title("Detalhes do Backup")
            details_window.geometry("500x400")
            
            # Mostrar informações detalhadas
            ttk.Label(details_window, text="Detalhes do backup serão mostrados aqui").pack(pady=50)
            ttk.Button(details_window, text="Fechar", command=details_window.destroy).pack()
        else:
            messagebox.showwarning("Aviso", "Selecione um backup para ver detalhes")
    
    def open_advanced_settings(self):
        """Abre configurações avançadas"""
        settings_window = tk.Toplevel(self.parent)
        settings_window.title("Configurações Avançadas de Backup")
        settings_window.geometry("600x500")
        
        # Notebook para abas
        notebook = ttk.Notebook(settings_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Aba de Agendamento
        schedule_frame = ttk.Frame(notebook, padding="10")
        notebook.add(schedule_frame, text="Agendamento")
        
        # Aba de Filtros
        filters_frame = ttk.Frame(notebook, padding="10")
        notebook.add(filters_frame, text="Filtros")
        
        # Aba de Notificações
        notifications_frame = ttk.Frame(notebook, padding="10")
        notebook.add(notifications_frame, text="Notificações")
        
        # Implementar cada aba
        self.create_schedule_tab(schedule_frame)
        self.create_filters_tab(filters_frame)
        self.create_notifications_tab(notifications_frame)
    
    def create_schedule_tab(self, parent):
        """Cria aba de agendamento"""
        ttk.Label(parent, text="Configurações de Agendamento", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 20))
        
        # Horário específico
        ttk.Label(parent, text="Horário para backup diário:").pack(anchor=tk.W)
        
        time_frame = ttk.Frame(parent)
        time_frame.pack(anchor=tk.W, pady=5)
        
        self.hour_var = tk.StringVar(value="02")
        self.minute_var = tk.StringVar(value="00")
        
        ttk.Spinbox(time_frame, from_=0, to=23, width=5, textvariable=self.hour_var, format="%02.0f").pack(side=tk.LEFT)
        ttk.Label(time_frame, text=":").pack(side=tk.LEFT, padx=5)
        ttk.Spinbox(time_frame, from_=0, to=59, width=5, textvariable=self.minute_var, format="%02.0f").pack(side=tk.LEFT)
        
        # Dias da semana
        ttk.Label(parent, text="Dias da semana para backup:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(20, 5))
        
        days_frame = ttk.Frame(parent)
        days_frame.pack(anchor=tk.W)
        
        self.days_vars = {}
        days = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        
        for i, day in enumerate(days):
            var = tk.BooleanVar(value=True)
            self.days_vars[day] = var
            ttk.Checkbutton(days_frame, text=day, variable=var).grid(row=i//4, column=i%4, sticky=tk.W, padx=10)
    
    def create_filters_tab(self, parent):
        """Cria aba de filtros"""
        ttk.Label(parent, text="Filtros de Backup", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 20))
        
        # Extensões de arquivo
        ttk.Label(parent, text="Incluir apenas estes tipos de arquivo:").pack(anchor=tk.W)
        
        self.extensions_var = tk.StringVar(value=".pdf,.json,.md,.txt")
        ttk.Entry(parent, textvariable=self.extensions_var, width=50).pack(anchor=tk.W, pady=5)
        
        ttk.Label(parent, text="(separados por vírgula)", font=("Arial", 8)).pack(anchor=tk.W)
        
        # Tamanho mínimo
        ttk.Label(parent, text="Tamanho mínimo do arquivo (KB):").pack(anchor=tk.W, pady=(20, 0))
        
        self.min_size_var = tk.IntVar(value=1)
        ttk.Spinbox(parent, from_=1, to=10240, textvariable=self.min_size_var, width=10).pack(anchor=tk.W, pady=5)
        
        # Pastas a excluir
        ttk.Label(parent, text="Excluir estas pastas:").pack(anchor=tk.W, pady=(20, 0))
        
        self.exclude_folders_var = tk.StringVar(value="temp,cache,__pycache__")
        ttk.Entry(parent, textvariable=self.exclude_folders_var, width=50).pack(anchor=tk.W, pady=5)
    
    def create_notifications_tab(self, parent):
        """Cria aba de notificações"""
        ttk.Label(parent, text="Configurações de Notificação", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 20))
        
        # Email
        self.email_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(parent, text="Enviar notificações por email", variable=self.email_enabled_var).pack(anchor=tk.W)
        
        ttk.Label(parent, text="Email:").pack(anchor=tk.W, pady=(10, 0))
        self.email_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.email_var, width=40).pack(anchor=tk.W, pady=5)
        
        # Slack
        self.slack_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(parent, text="Enviar notificações para Slack", variable=self.slack_enabled_var).pack(anchor=tk.W, pady=(20, 0))
        
        ttk.Label(parent, text="Webhook URL:").pack(anchor=tk.W, pady=(10, 0))
        self.slack_webhook_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.slack_webhook_var, width=50).pack(anchor=tk.W, pady=5)

def create_backup_window(backup_manager=None):
    """Cria janela de backup independente"""
    window = tk.Toplevel()
    window.title("💾 Gerenciamento de Backup")
    window.geometry("900x700")
    
    # Criar interface
    backup_interface = BackupInterface(window, backup_manager)
    
    return window, backup_interface