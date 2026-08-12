# -*- coding: utf-8 -*-
"""
Script to fix ONNX model IR version and Opset version for Jetson Nano (onnxruntime compatibility).
Converts any ONNX model IR version to <= 8 and opset_version to <= 11/15 so older Jetson onnxruntime can load it.
"""
import os
import sys

def fix_onnx_model_version(onnx_file_path, target_ir_version=8, target_opset_version=11):
    if not os.path.exists(onnx_file_path):
        print(f"[!] File not found: {onnx_file_path}")
        return False

    try:
        import onnx
        print(f"[*] Loading ONNX model from: {onnx_file_path}")
        model = onnx.load(onnx_file_path)
        
        current_ir = model.ir_version
        print(f"[*] Current Model IR Version: {current_ir}")
        
        # Downgrade Opset version if needed
        for imp in model.opset_import:
            if imp.domain == '' or imp.domain == 'ai.onnx':
                print(f"[*] Current Opset Version: {imp.version}")
                if imp.version > target_opset_version:
                    print(f"[*] Downgrading Opset Version from {imp.version} -> {target_opset_version} for Jetson compatibility...")
                    imp.version = target_opset_version

        # Downgrade IR version if needed
        if current_ir > target_ir_version:
            print(f"[*] Downgrading IR Version from {current_ir} -> {target_ir_version} for Jetson compatibility...")
            model.ir_version = target_ir_version

        onnx.save(model, onnx_file_path)
        print(f"🚀 [SUCCESS] Updated '{onnx_file_path}' (IR <= {target_ir_version}, Opset <= {target_opset_version})!")
        return True
    except ImportError:
        print("[!] Package 'onnx' is not installed.")
        return False

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base_dir, "road_following_model.onnx")
    fix_onnx_model_version(model_path)

