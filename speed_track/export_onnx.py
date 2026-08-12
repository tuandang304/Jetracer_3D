# -*- coding: utf-8 -*-
"""
Script to Export PyTorch Model (.pth) to ONNX (.onnx) for JetRacer Road Following.
Uses opset_version=10 and IR version 8 for full compatibility with Jetson JetPack onnxruntime.
"""
import os
import sys
import torch
import torchvision.models as models

def export_pytorch_to_onnx(model_pth_path, output_onnx_path, num_outputs=2):
    """
    Exports PyTorch model weights to ONNX format.
    Default input shape: (1, 3, 224, 224)
    Enforces opset_version=10 & IR version <= 8 for Jetson compatibility.
    """
    print("--------------------------------------------------")
    print(f"[*] Input PyTorch Model Path: {model_pth_path}")
    print(f"[*] Output ONNX Path: {output_onnx_path}")
    print("--------------------------------------------------")

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[*] Exporting device: {device}")

    # Build ResNet18 backbone (standard JetRacer architecture)
    model = models.resnet18(pretrained=False)
    model.fc = torch.nn.Linear(model.fc.in_features, num_outputs)

    if os.path.exists(model_pth_path):
        print(f"[+] Loading model weights from: {model_pth_path}")
        state_dict = torch.load(model_pth_path, map_location=device)
        model.load_state_dict(state_dict)
    else:
        print(f"[!] Warning: PyTorch model file '{model_pth_path}' not found! Creating random initialized model for ONNX export test...")

    model = model.to(device).eval()

    # Dummy input (1, 3, 224, 224)
    dummy_input = torch.randn(1, 3, 224, 224, device=device)

    # Export to ONNX with opset_version=10 (IR version 6/7)
    print("[*] Exporting model to ONNX format (opset_version=10)...")
    torch.onnx.export(
        model,
        dummy_input,
        output_onnx_path,
        export_params=True,
        opset_version=10,
        do_constant_folding=True,
        input_names=['input'],
        output_names=['output']
    )

    # Ensure IR version <= 8 using onnx library if present
    try:
        import onnx
        onnx_model = onnx.load(output_onnx_path)
        if onnx_model.ir_version > 8:
            print(f"[*] Downgrading ONNX IR version from {onnx_model.ir_version} -> 8 for Jetson compatibility...")
            onnx_model.ir_version = 8
            onnx.save(onnx_model, output_onnx_path)
    except Exception as e:
        print(f"[*] ONNX IR check notice: {e}")

    print(f"🚀 [SUCCESS] Exported ONNX model to '{output_onnx_path}' successfully!")

    # Verify ONNX model with ONNX Runtime if available
    try:
        import onnxruntime as ort
        session = ort.InferenceSession(output_onnx_path, providers=['CPUExecutionProvider'])
        print(f"[+] ONNX Runtime verification: Model loaded successfully with providers {session.get_providers()}!")
    except Exception as e:
        print(f"[*] ONNX Verification notice: {e}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_pth = os.path.join(base_dir, "road_following_model.pth")
    output_onnx = os.path.join(base_dir, "road_following_model.onnx")
    
    export_pytorch_to_onnx(input_pth, output_onnx)
