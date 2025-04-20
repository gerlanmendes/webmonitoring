import time
import datetime
import requests
import schedule
import os
from pymongo import MongoClient
from icmplib import ping

# Sites a serem monitorados
SITES = ["google.com", "youtube.com", "rnp.br"]

# Configuração do MongoDB
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongodb:27017/")
MONGO_DB = os.environ.get("MONGO_DB", "monitoring")
MONGO_PING_COLLECTION = "ping_results"
MONGO_HTTP_COLLECTION = "http_results"

# Intervalo entre verificações (em segundos)
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "60"))

def connect_to_db():
    """Conectar ao banco de dados MongoDB"""
    try:
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        print(f"Conectado ao MongoDB: {MONGO_URI}")
        return db
    except Exception as e:
        print(f"Erro ao conectar ao MongoDB: {e}")
        return None

def perform_ping_test(host):
    """Realizar teste de ping e retornar os resultados"""
    try:
        # Realiza 4 pings para cada host
        ping_result = ping(host, count=4, interval=0.5, timeout=2)
        
        result = {
            "timestamp": datetime.datetime.utcnow(),
            "host": host,
            "min_rtt": ping_result.min_rtt,
            "max_rtt": ping_result.max_rtt,
            "avg_rtt": ping_result.avg_rtt,
            "packet_loss": ping_result.packet_loss * 100  # Converter para porcentagem
        }
        return result
    except Exception as e:
        print(f"Erro ao realizar ping para {host}: {e}")
        return {
            "timestamp": datetime.datetime.utcnow(),
            "host": host,
            "error": str(e),
            "packet_loss": 100.0  # Consideramos 100% de perda em caso de erro
        }

def perform_http_test(url):
    """Realizar teste de carregamento de página e retornar os resultados"""
    if not url.startswith("http"):
        url = f"https://{url}"
    
    try:
        start_time = time.time()
        response = requests.get(url, timeout=10)
        load_time = time.time() - start_time
        
        result = {
            "timestamp": datetime.datetime.utcnow(),
            "url": url,
            "status_code": response.status_code,
            "load_time_ms": load_time * 1000,  # Converter para milissegundos
            "response_size_bytes": len(response.content)
        }
        return result
    except Exception as e:
        print(f"Erro ao acessar {url}: {e}")
        return {
            "timestamp": datetime.datetime.utcnow(),
            "url": url,
            "error": str(e),
            "status_code": 0,
            "load_time_ms": -1
        }

def run_checks():
    """Executar todas as verificações e salvar no banco de dados"""
    db = connect_to_db()
    if not db:
        print("Não foi possível conectar ao banco de dados. Tentando novamente mais tarde.")
        return
    
    # Coleções para armazenar os resultados
    ping_collection = db[MONGO_PING_COLLECTION]
    http_collection = db[MONGO_HTTP_COLLECTION]
    
    print(f"Iniciando verificações em {datetime.datetime.now()}")
    
    # Realizar testes de ping
    for site in SITES:
        ping_result = perform_ping_test(site)
        ping_collection.insert_one(ping_result)
        print(f"Ping para {site}: RTT médio = {ping_result.get('avg_rtt', 'N/A'):.2f}ms, " 
              f"Perda de pacotes = {ping_result.get('packet_loss', 'N/A'):.2f}%")
    
    # Realizar testes HTTP
    for site in SITES:
        http_result = perform_http_test(site)
        http_collection.insert_one(http_result)
        print(f"HTTP para {site}: Status = {http_result.get('status_code', 'N/A')}, " 
              f"Tempo de carregamento = {http_result.get('load_time_ms', 'N/A'):.2f}ms")
    
    print(f"Verificações concluídas em {datetime.datetime.now()}")

def main():
    """Função principal para agendar verificações periódicas"""
    print(f"Iniciando o agente de monitoramento - Intervalo de verificação: {CHECK_INTERVAL} segundos")
    
    # Executar imediatamente na inicialização
    run_checks()
    
    # Agendar execução periódica
    schedule.every(CHECK_INTERVAL).seconds.do(run_checks)
    
    # Loop principal
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    # Aguardar alguns segundos para garantir que o MongoDB esteja pronto
    time.sleep(5)
    main()minha mãe não quer 