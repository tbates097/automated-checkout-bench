# -*- coding: utf-8 -*-
"""
Shared registry for secondary UI instance to avoid module import issues.
"""

# Global registry for secondary UI instance
_secondary_ui_instance = None

def get_secondary_ui():
    """Get the secondary UI instance from the shared registry"""
    return _secondary_ui_instance

def set_secondary_ui(instance):
    """Set the secondary UI instance in the shared registry"""
    global _secondary_ui_instance
    _secondary_ui_instance = instance
    print(f"DEBUG: Set secondary UI in registry: {instance}")

def clear_secondary_ui():
    """Clear the secondary UI instance from the registry"""
    global _secondary_ui_instance
    _secondary_ui_instance = None