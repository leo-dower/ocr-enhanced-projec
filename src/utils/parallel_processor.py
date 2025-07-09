"""
Sistema de Processamento Paralelo para OCR Enhanced.

Este módulo implementa processamento paralelo de múltiplos arquivos
com controle de concorrência, timeouts e monitoramento em tempo real.
"""

import threading
import time
import queue
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Union
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass, field
import os
import sys
from datetime import datetime

from .logger import get_logger


@dataclass
class ProcessingTask:
    """Representação de uma tarefa de processamento."""
    
    file_path: Path
    task_id: str
    options: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    created_at: float = field(default_factory=time.time)
    timeout: Optional[float] = None
    
    def __post_init__(self):
        """Validar e normalizar dados da tarefa."""
        if isinstance(self.file_path, str):
            self.file_path = Path(self.file_path)
        
        if not self.task_id:
            self.task_id = f"{self.file_path.name}_{int(time.time())}"


@dataclass
class ProcessingResult:
    """Resultado de uma tarefa de processamento."""
    
    task_id: str
    file_path: Path
    success: bool
    result: Any = None
    error: Optional[str] = None
    processing_time: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    worker_id: Optional[str] = None
    from_cache: bool = False
    
    def __post_init__(self):
        """Calcular métricas derivadas."""
        if self.started_at and self.completed_at:
            self.processing_time = self.completed_at - self.started_at


@dataclass
class ProcessingStats:
    """Estatísticas de processamento."""
    
    total_tasks: int = 0
    completed_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    cache_hits: int = 0
    
    total_processing_time: float = 0.0
    avg_processing_time: float = 0.0
    
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    def update(self, result: ProcessingResult):
        """Atualizar estatísticas com resultado."""
        self.completed_tasks += 1
        
        if result.success:
            self.successful_tasks += 1
        else:
            self.failed_tasks += 1
        
        if result.from_cache:
            self.cache_hits += 1
        
        self.total_processing_time += result.processing_time
        
        if self.completed_tasks > 0:
            self.avg_processing_time = self.total_processing_time / self.completed_tasks
    
    @property
    def success_rate(self) -> float:
        """Taxa de sucesso."""
        return self.successful_tasks / max(self.completed_tasks, 1)
    
    @property
    def cache_hit_rate(self) -> float:
        """Taxa de acerto do cache."""
        return self.cache_hits / max(self.completed_tasks, 1)
    
    @property
    def elapsed_time(self) -> float:
        """Tempo decorrido total."""
        if self.start_time is None:
            return 0.0
        
        end = self.end_time or time.time()
        return end - self.start_time
    
    @property
    def throughput(self) -> float:
        """Arquivos processados por segundo."""
        elapsed = self.elapsed_time
        return self.completed_tasks / max(elapsed, 1)


class ParallelProcessor:
    """
    Processador paralelo para múltiplos arquivos OCR.
    
    Funcionalidades:
    - ThreadPool configurável
    - Controle de concorrência
    - Timeouts individuais por arquivo
    - Monitoramento em tempo real
    - Integração com cache
    - Priorização de tarefas
    """
    
    def __init__(self, 
                 max_workers: int = 4,
                 timeout_per_file: float = 300.0,
                 progress_callback: Optional[Callable] = None):
        """
        Inicializar processador paralelo.
        
        Args:
            max_workers: Número máximo de workers simultâneos
            timeout_per_file: Timeout padrão por arquivo (segundos)
            progress_callback: Função para receber updates de progresso
        """
        self.max_workers = max_workers
        self.timeout_per_file = timeout_per_file
        self.progress_callback = progress_callback
        self.logger = get_logger("parallel_processor")
        
        # Estado do processamento
        self.is_running = False
        self.executor: Optional[ThreadPoolExecutor] = None
        self.tasks_queue: queue.PriorityQueue = queue.PriorityQueue()
        self.results_queue: queue.Queue = queue.Queue()
        
        # Controle de progresso
        self.stats = ProcessingStats()
        self.active_futures: Dict[str, Future] = {}
        self.progress_lock = threading.Lock()
        
        # Configurações avançadas
        self.auto_adjust_workers = True
        self.min_workers = 1
        self.max_workers_limit = os.cpu_count() or 4
        
        self.logger.info(f"Processador paralelo inicializado: {max_workers} workers")
    
    def add_task(self, file_path: Union[str, Path], 
                 options: Dict[str, Any] = None,
                 priority: int = 0,
                 timeout: Optional[float] = None) -> str:
        """
        Adicionar tarefa à fila de processamento.
        
        Args:
            file_path: Caminho para o arquivo
            options: Opções de processamento
            priority: Prioridade da tarefa (menor = maior prioridade)
            timeout: Timeout específico para esta tarefa
            
        Returns:
            ID da tarefa
        """
        task = ProcessingTask(
            file_path=Path(file_path),
            task_id=f"{Path(file_path).name}_{int(time.time())}_{id(self)}",
            options=options or {},
            priority=priority,
            timeout=timeout or self.timeout_per_file
        )
        
        # Adicionar à fila (PriorityQueue usa tupla para ordenação)
        self.tasks_queue.put((priority, task.created_at, task))
        
        with self.progress_lock:
            self.stats.total_tasks += 1
        
        self.logger.debug(f"Tarefa adicionada: {task.task_id}")
        return task.task_id
    
    def add_batch(self, file_paths: List[Union[str, Path]], 
                  options: Dict[str, Any] = None,
                  priority: int = 0) -> List[str]:
        """
        Adicionar lote de arquivos para processamento.
        
        Args:
            file_paths: Lista de caminhos para arquivos
            options: Opções de processamento
            priority: Prioridade base das tarefas
            
        Returns:
            Lista de IDs das tarefas
        """
        task_ids = []
        
        for i, file_path in enumerate(file_paths):
            # Prioridade ligeiramente diferente para cada arquivo
            task_priority = priority + (i * 0.01)
            task_id = self.add_task(file_path, options, task_priority)
            task_ids.append(task_id)
        
        self.logger.info(f"Lote adicionado: {len(file_paths)} arquivos")
        return task_ids
    
    def process_batch(self, 
                     processor_function: Callable,
                     max_retries: int = 3) -> List[ProcessingResult]:
        """
        Processar todas as tarefas na fila.
        
        Args:
            processor_function: Função que processa um arquivo
            max_retries: Número máximo de tentativas por arquivo
            
        Returns:
            Lista de resultados
        """
        if self.is_running:
            raise RuntimeError("Processador já está executando")
        
        self.is_running = True
        self.stats.start_time = time.time()
        
        try:
            return self._execute_batch(processor_function, max_retries)
        finally:
            self.is_running = False
            self.stats.end_time = time.time()
    
    def _execute_batch(self, processor_function: Callable, 
                      max_retries: int) -> List[ProcessingResult]:
        """Executar processamento em lote."""
        results = []
        
        # Determinar número otimizado de workers
        num_workers = self._calculate_optimal_workers()
        
        self.logger.info(f"Iniciando processamento com {num_workers} workers")
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            self.executor = executor
            
            # Processar todas as tarefas
            while not self.tasks_queue.empty():
                batch_results = self._process_task_batch(
                    processor_function, max_retries
                )
                results.extend(batch_results)
                
                # Atualizar progresso
                self._update_progress(batch_results)
        
        self.executor = None
        
        self.logger.info(f"Processamento concluído: {len(results)} arquivos")
        return results
    
    def _process_task_batch(self, processor_function: Callable, 
                           max_retries: int) -> List[ProcessingResult]:
        """Processar um lote de tarefas."""
        # Coletar tarefas para processar
        tasks_to_process = []
        
        # Coletar até max_workers tarefas
        for _ in range(self.max_workers):
            try:
                _, _, task = self.tasks_queue.get_nowait()
                tasks_to_process.append(task)
            except queue.Empty:
                break
        
        if not tasks_to_process:
            return []
        
        # Submeter tarefas para execução
        future_to_task = {}
        
        for task in tasks_to_process:
            future = self.executor.submit(
                self._process_single_task, 
                task, processor_function, max_retries
            )
            future_to_task[future] = task
            self.active_futures[task.task_id] = future
        
        # Coletar resultados
        results = []
        
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            
            try:
                result = future.result()
                results.append(result)
                
                # Remover do tracking
                self.active_futures.pop(task.task_id, None)
                
            except Exception as e:
                self.logger.error(f"Erro inesperado na tarefa {task.task_id}: {e}")
                
                # Criar resultado de erro
                error_result = ProcessingResult(
                    task_id=task.task_id,
                    file_path=task.file_path,
                    success=False,
                    error=str(e),
                    processing_time=0.0,
                    started_at=time.time(),
                    completed_at=time.time()
                )
                results.append(error_result)
        
        return results
    
    def _process_single_task(self, task: ProcessingTask, 
                            processor_function: Callable,
                            max_retries: int) -> ProcessingResult:
        """Processar uma única tarefa."""
        worker_id = threading.current_thread().name
        started_at = time.time()
        
        self.logger.debug(f"Iniciando processamento: {task.task_id} (worker: {worker_id})")
        
        for attempt in range(max_retries + 1):
            try:
                # Verificar se deve cancelar
                if not self.is_running:
                    raise InterruptedError("Processamento cancelado")
                
                # Processar arquivo
                result = processor_function(task.file_path, task.options)
                
                # Sucesso
                completed_at = time.time()
                
                return ProcessingResult(
                    task_id=task.task_id,
                    file_path=task.file_path,
                    success=True,
                    result=result,
                    processing_time=completed_at - started_at,
                    started_at=started_at,
                    completed_at=completed_at,
                    worker_id=worker_id,
                    from_cache=self._is_from_cache(result)
                )
                
            except Exception as e:
                error_msg = str(e)
                
                if attempt < max_retries:
                    self.logger.warning(f"Tentativa {attempt + 1} falhou para {task.task_id}: {error_msg}")
                    time.sleep(2 ** attempt)  # Backoff exponencial
                else:
                    self.logger.error(f"Todas as tentativas falharam para {task.task_id}: {error_msg}")
                    
                    return ProcessingResult(
                        task_id=task.task_id,
                        file_path=task.file_path,
                        success=False,
                        error=error_msg,
                        processing_time=time.time() - started_at,
                        started_at=started_at,
                        completed_at=time.time(),
                        worker_id=worker_id
                    )
        
        # Fallback (não deveria chegar aqui)
        return ProcessingResult(
            task_id=task.task_id,
            file_path=task.file_path,
            success=False,
            error="Erro desconhecido",
            processing_time=time.time() - started_at,
            started_at=started_at,
            completed_at=time.time(),
            worker_id=worker_id
        )
    
    def _is_from_cache(self, result: Any) -> bool:
        """Verificar se resultado veio do cache."""
        if isinstance(result, dict):
            # Verificar se contém indicadores de cache
            metadata = result.get('metadata', {})
            return 'cached' in metadata.get('method', '').lower()
        
        # Para OCRResult objects
        if hasattr(result, 'processing_time'):
            # Cache geralmente é muito mais rápido
            return result.processing_time < 0.1
        
        return False
    
    def _calculate_optimal_workers(self) -> int:
        """Calcular número otimizado de workers baseado na carga."""
        if not self.auto_adjust_workers:
            return self.max_workers
        
        # Começar com número configurado
        optimal = self.max_workers
        
        # Ajustar baseado no número de tarefas
        queue_size = self.tasks_queue.qsize()
        
        if queue_size < 3:
            optimal = min(optimal, 2)
        elif queue_size > 10:
            optimal = min(optimal + 2, self.max_workers_limit)
        
        # Respeitar limites
        optimal = max(self.min_workers, min(optimal, self.max_workers_limit))
        
        return optimal
    
    def _update_progress(self, results: List[ProcessingResult]):
        """Atualizar progresso com thread safety."""
        with self.progress_lock:
            for result in results:
                self.stats.update(result)
            
            # Callback de progresso
            if self.progress_callback:
                try:
                    progress_info = {
                        'completed': self.stats.completed_tasks,
                        'total': self.stats.total_tasks,
                        'success_rate': self.stats.success_rate,
                        'cache_hit_rate': self.stats.cache_hit_rate,
                        'avg_time': self.stats.avg_processing_time,
                        'throughput': self.stats.throughput,
                        'elapsed': self.stats.elapsed_time
                    }
                    
                    self.progress_callback(progress_info)
                    
                except Exception as e:
                    self.logger.warning(f"Erro no callback de progresso: {e}")
    
    def cancel_processing(self) -> bool:
        """Cancelar processamento em andamento."""
        if not self.is_running:
            return False
        
        self.is_running = False
        
        # Cancelar futures ativos
        for future in self.active_futures.values():
            future.cancel()
        
        self.logger.info("Processamento cancelado")
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Obter estatísticas detalhadas."""
        with self.progress_lock:
            return {
                'total_tasks': self.stats.total_tasks,
                'completed_tasks': self.stats.completed_tasks,
                'successful_tasks': self.stats.successful_tasks,
                'failed_tasks': self.stats.failed_tasks,
                'cache_hits': self.stats.cache_hits,
                
                'success_rate': self.stats.success_rate,
                'cache_hit_rate': self.stats.cache_hit_rate,
                
                'total_processing_time': self.stats.total_processing_time,
                'avg_processing_time': self.stats.avg_processing_time,
                'throughput': self.stats.throughput,
                'elapsed_time': self.stats.elapsed_time,
                
                'is_running': self.is_running,
                'active_tasks': len(self.active_futures),
                'pending_tasks': self.tasks_queue.qsize(),
                
                'workers_config': {
                    'max_workers': self.max_workers,
                    'auto_adjust': self.auto_adjust_workers,
                    'timeout_per_file': self.timeout_per_file
                }
            }
    
    def get_progress_percentage(self) -> float:
        """Obter porcentagem de progresso."""
        with self.progress_lock:
            if self.stats.total_tasks == 0:
                return 0.0
            
            return (self.stats.completed_tasks / self.stats.total_tasks) * 100.0
    
    def clear_queue(self):
        """Limpar fila de tarefas."""
        while not self.tasks_queue.empty():
            try:
                self.tasks_queue.get_nowait()
            except queue.Empty:
                break
        
        with self.progress_lock:
            self.stats = ProcessingStats()
        
        self.logger.info("Fila de tarefas limpa")


# Factory function
def create_parallel_processor(max_workers: int = 4,
                            timeout_per_file: float = 300.0,
                            progress_callback: Optional[Callable] = None) -> ParallelProcessor:
    """Criar instância do processador paralelo."""
    return ParallelProcessor(max_workers, timeout_per_file, progress_callback)


# Example usage
if __name__ == "__main__":
    # Exemplo de uso
    def mock_processor(file_path, options):
        """Processador mock para demonstração."""
        print(f"Processando: {file_path}")
        time.sleep(1)  # Simular processamento
        return {"success": True, "text": f"Resultado para {file_path}"}
    
    def progress_callback(info):
        """Callback de progresso."""
        print(f"Progresso: {info['completed']}/{info['total']} "
              f"({info['completed']/info['total']*100:.1f}%)")
    
    # Criar processador
    processor = create_parallel_processor(
        max_workers=3,
        progress_callback=progress_callback
    )
    
    # Adicionar tarefas
    test_files = [f"test_{i}.pdf" for i in range(10)]
    processor.add_batch(test_files)
    
    # Processar
    results = processor.process_batch(mock_processor)
    
    # Estatísticas
    stats = processor.get_statistics()
    print(f"\nEstatísticas:")
    print(f"Sucessos: {stats['successful_tasks']}/{stats['total_tasks']}")
    print(f"Tempo médio: {stats['avg_processing_time']:.2f}s")
    print(f"Throughput: {stats['throughput']:.2f} arquivos/s")