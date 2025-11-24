"""
Sistema de Logging Centralizado - Dashboard-TRONIK
==================================================
Configuração centralizada de logging para toda a aplicação.
"""

import logging
import sys
from typing import Optional
from logging.handlers import RotatingFileHandler
import os


def configurar_logging(
    nivel: str = "INFO",
    arquivo_log: Optional[str] = None,
    formato: Optional[str] = None
) -> None:
    """
    Configura o sistema de logging da aplicação.
    
    Args:
        nivel: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        arquivo_log: Caminho do arquivo de log (opcional)
        formato: Formato personalizado (opcional)
    """
    # Formato padrão
    if formato is None:
        formato = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Nível de log
    nivel_log = getattr(logging, nivel.upper(), logging.INFO)
    
    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(nivel_log)
    
    # Remover handlers existentes
    root_logger.handlers.clear()
    
    # Handler para console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(nivel_log)
    console_handler.setFormatter(logging.Formatter(formato))
    root_logger.addHandler(console_handler)
    
    # Handler para arquivo (se especificado)
    if arquivo_log:
        # Criar diretório se não existir
        log_dir = os.path.dirname(arquivo_log)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Rotating file handler (10MB por arquivo, 5 backups)
        file_handler = RotatingFileHandler(
            arquivo_log,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(nivel_log)
        file_handler.setFormatter(logging.Formatter(formato))
        root_logger.addHandler(file_handler)


def obter_logger(nome: str) -> logging.Logger:
    """
    Obtém um logger com o nome especificado.
    
    Args:
        nome: Nome do logger (geralmente __name__)
    
    Returns:
        Logger configurado
    """
    return logging.getLogger(nome)

