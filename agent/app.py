import os
import time
import subprocess
import requests
from datetime import datetime
from influxdb import InfluxDBClient
import re
import logging

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('monitoring_agent')

# Parâmetros de configuração
PING_TARGETS = ['google.com', 'youtube.com', 'rnp.br']
WEB_TARGETS = ['https://google.com', 'https://youtube.com', 'https://rnp.br']
INFLUXDB_HOST = os.environ.get('INFLUXDB_HOST', 'influxdb')
INFLUXDB_PORT = int(os.environ.get('INFLUXDB_PORT', 8086))
INFLUXDB_USER = os.environ.get('INFLUXDB_USER', 'admin')
INFLUXDB_PASSWORD = os.environ.get('INFLUXDB_PASSWORD', 'admin')
INFLUXDB_DATABASE = os.environ.get('INFLUXDB_DATABASE', 'network_monitoring')
CHECK_INTERVAL = int(os.environ.get('CHECK_INTERVAL', 60))  # segundos

# Função para conectar ao InfluxDB
def get_influxdb_client():
    client = InfluxDBClient(
        host=INFLUXDB_HOST,
        port=INFLUXDB_PORT,
        username=INFLUXDB_USER,
        password=INFLUXDB_PASSWORD
    )
    
    # Verifica se o banco de dados existe, se não, cria
    databases = client.get_list_database()
    if {'name': INFLUXDB_DATABASE} not in databases:
        logger.info(f"Criando banco de dados: {INFLUXDB_DATABASE}")
        client.create_database(INFLUXDB_DATABASE)
    
    client.switch_database(INFLUXDB_DATABASE)
    return client

# Função para executar ping e extrair resultados
def run_ping_test(target, count=10):
    try:
        logger.info(f"Executando ping para {target}")
        output = subprocess.check_output(
            ['ping', '-c', str(count), target], 
            universal_newlines=True
        )
        
        # Extrair RTT médio
        rtt_match = re.search(r'min/avg/max/mdev = \d+\.\d+/(\d+\.\d+)/\d+\.\d+/\d+\.\d+', output)
        rtt = float(rtt_match.group(1)) if rtt_match else None
        
        # Extrair perda de pacotes
        packet_loss_match = re.search(r'(\d+)% packet loss', output)
        packet_loss = float(packet_loss_match.group(1)) if packet_loss_match else None
        
        return {
            'rtt': rtt,
            'packet_loss': packet_loss
        }
    except Exception as e:
        logger.error(f"Erro ao realizar ping para {target}: {e}")
        return {
            'rtt': None,
            'packet_loss': 100.0  # consideramos 100% de perda em caso de erro
        }

# Função para verificar sites web
def check_website(url):
    try:
        logger.info(f"Verificando website: {url}")
        start_time = time.time()
        response = requests.get(url, timeout=10)
        load_time = time.time() - start_time
        
        return {
            'status_code': response.status_code,
            'load_time': load_time
        }
    except Exception as e:
        logger.error(f"Erro ao verificar website {url}: {e}")
        return {
            'status_code': 0,  # 0 indica erro de conexão
            'load_time': None
        }

# Função para formatar os dados para o InfluxDB
def format_ping_data(target, results):
    timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    return {
        "measurement": "ping_metrics",
        "tags": {
            "target": target
        },
        "time": timestamp,
        "fields": {
            "rtt": results["rtt"] if results["rtt"] is not None else 0,
            "packet_loss": results["packet_loss"]
        }
    }

def format_web_data(url, results):
    timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    domain = url.split('://')[1].split('/')[0]
    return {
        "measurement": "web_metrics",
        "tags": {
            "url": url,
            "domain": domain
        },
        "time": timestamp,
        "fields": {
            "status_code": results["status_code"],
            "load_time": results["load_time"] if results["load_time"] is not None else 0
        }
    }

# Função principal
def main():
    logger.info("Iniciando agente de monitoramento web")
    
    # Conectar ao InfluxDB
    while True:
        try:
            client = get_influxdb_client()
            logger.info("Conectado ao InfluxDB com sucesso")
            break
        except Exception as e:
            logger.error(f"Erro ao conectar ao InfluxDB: {e}")
            logger.info("Tentando novamente em 10 segundos...")
            time.sleep(10)
    
    # Loop principal
    while True:
        influx_data = []
        
        # Executar testes de ping
        for target in PING_TARGETS:
            ping_results = run_ping_test(target)
            influx_data.append(format_ping_data(target, ping_results))
        
        # Verificar websites
        for url in WEB_TARGETS:
            web_results = check_website(url)
            influx_data.append(format_web_data(url, web_results))
        
        # Enviar dados para o InfluxDB
        try:
            client.write_points(influx_data)
            logger.info(f"Dados enviados para o InfluxDB: {len(influx_data)} pontos")
        except Exception as e:
            logger.error(f"Erro ao enviar dados para o InfluxDB: {e}")
        
        # Aguardar até o próximo ciclo
        logger.info(f"Aguardando {CHECK_INTERVAL} segundos até o próximo ciclo")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()