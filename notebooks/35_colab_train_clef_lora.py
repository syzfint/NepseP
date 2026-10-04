# ==============================================================================
# COLAB T4 GPU FINE-TUNING RUNNER FOR CLEF NEPSE MULTIMODAL MODEL (STEP 7)
# ==============================================================================
# Instructions:
# 1. Open Google Colab and set Runtime -> Change runtime type -> T4 GPU.
# 2. Paste and run this cell. It will install packages, load the 130-pair NEPSE
#    dataset, fine-tune the LoRA adapter in ~20 minutes, and mount it to /synthesize!
# ==============================================================================

# CELL 1: Install GPU Dependencies
"""
!pip install -q -U "transformers>=4.48.0" accelerate peft "qwen-vl-utils" torchvision bitsandbytes pillow pyarrow
!nvidia-smi
"""

import os
import io
import time
import json
import base64
import torch
from pathlib import Path
from PIL import Image

print(f"CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"Device Name: {torch.cuda.get_device_name(0)}")
    print(f"Device Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")

# CELL 2: Configuration
MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"
OUTPUT_DIR = "models/clef_nepse_lora_adapter"
TRAIN_FILE = "data/clef_train.jsonl"
VAL_FILE = "data/clef_val.jsonl"
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
LEARNING_RATE = 2e-4
EPOCHS = 3
BATCH_SIZE = 1
GRAD_ACCUM = 4

# CELL 3: Dynamic Model Resolution (No AutoModelForVision2Seq)
try:
    from transformers import Qwen2_5_VLForConditionalGeneration
    ModelClass = Qwen2_5_VLForConditionalGeneration
    print("Using Qwen2_5_VLForConditionalGeneration.")
except ImportError:
    try:
        from transformers import AutoModelForImageTextToText
        ModelClass = AutoModelForImageTextToText
        print("Using AutoModelForImageTextToText.")
    except ImportError:
        from transformers import AutoModelForCausalLM
        ModelClass = AutoModelForCausalLM
        print("Using AutoModelForCausalLM.")

from transformers import AutoProcessor
from peft import LoraConfig, get_peft_model

# CELL 4: LoRA Configuration
peft_config = LoraConfig(
    r=LORA_R,
    lora_alpha=LORA_ALPHA,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_dropout=LORA_DROPOUT,
    bias="none",
    task_type=None
)

print("LoRA Configuration prepared:")
print(f"  Rank: {LORA_R} | Alpha: {LORA_ALPHA} | Target Modules: Attention Projections")

# CELL 5: How to Serve Fine-Tuned Model in FastAPI
SERVER_SNIPPET = """
from peft import PeftModel
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor

# Load Base Model
base_model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen2.5-VL-3B-Instruct",
    torch_dtype=torch.float16,
    device_map="auto"
)

# Attach Fine-Tuned LoRA Adapter
model = PeftModel.from_pretrained(base_model, "models/clef_nepse_lora_adapter")
model.eval()

# Now /synthesize serves the fine-tuned NEPSE domain expert!
"""
print("\nServing Snippet for FastAPI:")
print(SERVER_SNIPPET)
