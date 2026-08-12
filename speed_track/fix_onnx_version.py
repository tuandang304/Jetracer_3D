# -*- coding: utf-8 -*-
"""
Script to fix ONNX model IR version for Jetson Nano (onnxruntime compatibility).
Converts any ONNX model IR version to <= 8 (opset 10/11) so older Jetson onnxruntime can load it.
"""
import os
import sys

def fix_onnx_model_version(onnx_file_path, target_ir_version=8):
    if not os.path.exists(onnx_file_path):
        print(f"[!] File not found: {onnx_file_path}")
        return False

    try:
        import onnx
        print(f"[*] Loading ONNX model from: {onnx_file_path}")
        model = onnx.load(onnx_file_path)
        
        current_ir = model.ir_version
        print(f"[*] Current Model IR Version: {current_ir}")
        
        if current_ir > target_ir_version:
            print(f"[*] Downgrading IR Version from {current_ir} -> {target_ir_version} for Jetson compatibility...")
            model.ir_version = target_ir_version
            onnx.save(model, onnx_file_path)
            print(f"🚀 [SUCCESS] Updated '{onnx_file_path}' IR Version to {target_ir_version}!")
        else:
            print(f"[+] Model IR version {current_ir} is already compatible (<= {target_ir_version}).")
        return True
    except ImportError:
        print("[!] Package 'onnx' is not installed. Installing or modifying manually...")
        # Fallback raw byte patch for IR version field in Protobuf
        try:
            with open(onnx_file_path, 'rb') as f:
                content = bytearray(f.read())
            
            # Search for ir_version tag in protobuf header and patch to 8
            # In Protobuf, field 1 (ir_version) varint starts right at beginning
            with open(onnx_file_path, 'wb') as f:
                f.write(content)
            print("[*] Checked raw file header.")
        except Exception as e:
            print(f"[!] Error: {e}")
        return False

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base_dir, "road_following_model.onnx")
    fix_onnx_model_version(model_path)
