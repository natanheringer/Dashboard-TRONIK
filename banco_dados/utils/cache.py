"""
Sistema de Cache - Dashboard-TRONIK
===================================
Cache simples em memória para dados estáticos.
"""

from typing import Dict, Optional, Any, Callable
from datetime import datetime, timedelta
import threading
import logging

logger = logging.getLogger(__name__)


class CacheMemoria:
    """Cache simples em memória com TTL"""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
    
    def obter(self, chave: str, ttl_segundos: int = 3600) -> Optional[Any]:
        """
        Obtém valor do cache se ainda válido.
        
        Args:
            chave: Chave do cache
            ttl_segundos: Tempo de vida em segundos (padrão: 1 hora)
        
        Returns:
            Valor do cache ou None se expirado/não existe
        """
        with self._lock:
            if chave not in self._cache:
                return None
            
            entrada = self._cache[chave]
            expiracao = entrada['criado_em'] + timedelta(seconds=ttl_segundos)
            
            if datetime.now() > expiracao:
                # Expirado - remover
                del self._cache[chave]
                return None
            
            return entrada['valor']
    
    def definir(self, chave: str, valor: Any) -> None:
        """
        Define valor no cache.
        
        Args:
            chave: Chave do cache
            valor: Valor a armazenar
        """
        with self._lock:
            self._cache[chave] = {
                'valor': valor,
                'criado_em': datetime.now()
            }
    
    def invalidar(self, chave: str) -> None:
        """
        Remove entrada do cache.
        
        Args:
            chave: Chave do cache
        """
        with self._lock:
            if chave in self._cache:
                del self._cache[chave]
    
    def limpar(self) -> None:
        """Limpa todo o cache"""
        with self._lock:
            self._cache.clear()
    
    def obter_ou_calcular(
        self,
        chave: str,
        calcular_fn: Callable[[], Any],
        ttl_segundos: int = 3600
    ) -> Any:
        """
        Obtém do cache ou calcula e armazena.
        
        Args:
            chave: Chave do cache
            calcular_fn: Função para calcular valor se não estiver no cache
            ttl_segundos: Tempo de vida em segundos
        
        Returns:
            Valor do cache ou calculado
        """
        valor = self.obter(chave, ttl_segundos)
        if valor is not None:
            return valor
        
        # Calcular e armazenar
        valor = calcular_fn()
        self.definir(chave, valor)
        return valor


# Instância global do cache
_cache_global = CacheMemoria()


def obter_cache() -> CacheMemoria:
    """Obtém instância global do cache"""
    return _cache_global

