"""One-time public model download before uploading internal documents."""
import os
import subprocess
import argparse
from pathlib import Path

root = Path(__file__).resolve().parents[1]
os.chdir(root)
compose = ['docker','compose','-f','docker-compose.yml','-f','docker-compose.bootstrap.yml']
parser = argparse.ArgumentParser()
parser.add_argument('--skip-build', action='store_true', help='Reuse an existing inference image.')
args = parser.parse_args()
if not args.skip_build:
    subprocess.run(compose+['build','inference'],check=True)
subprocess.run(compose+['run','--rm','--no-deps','inference','python','-c',
    "from huggingface_hub import snapshot_download; patterns=['*.json','*.model','pytorch_model.bin','model.safetensors']; "
    "snapshot_download('BAAI/bge-m3',local_dir='/models/bge-m3',allow_patterns=patterns,ignore_patterns=['onnx/*','openvino/*'],max_workers=2); "
    "snapshot_download('BAAI/bge-reranker-v2-m3',local_dir='/models/bge-reranker-v2-m3',allow_patterns=patterns,ignore_patterns=['onnx/*','openvino/*'],max_workers=2)"],check=True)
print('Modèles disponibles. Utiliser maintenant le compose standard (réseau interne).')
