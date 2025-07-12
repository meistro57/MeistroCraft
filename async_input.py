#!/usr/bin/env python3
"""
Async Input Handler for MeistroCraft Terminal UI
Handles non-blocking user input for the split terminal interface.
"""

import sys
import threading
import queue
from typing import Callable, Optional

# Import platform-specific modules
try:
    import select
    import termios
    import tty
    UNIX_AVAILABLE = True
except ImportError:
    UNIX_AVAILABLE = False

class AsyncInputHandler:
    """Handles asynchronous user input without blocking the UI."""
    
    def __init__(self, input_callback: Callable[[str], None]):
        self.input_callback = input_callback
        self.running = False
        self.input_thread = None
        self.input_queue = queue.Queue()
        self.current_line = ""
        
        # Terminal settings for raw input
        self.old_settings = None
        
    def start(self) -> None:
        """Start the async input handler."""
        self.running = True
        
        # Save terminal settings
        if UNIX_AVAILABLE and sys.stdin.isatty():
            self.old_settings = termios.tcgetattr(sys.stdin)
        
        # Start input thread
        self.input_thread = threading.Thread(target=self._input_loop, daemon=True)
        self.input_thread.start()
    
    def stop(self) -> None:
        """Stop the async input handler."""
        self.running = False
        
        # Restore terminal settings
        if UNIX_AVAILABLE and self.old_settings and sys.stdin.isatty():
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
        
        # Wait for thread to finish
        if self.input_thread and self.input_thread.is_alive():
            self.input_thread.join(timeout=1.0)
    
    def _input_loop(self) -> None:
        """Main input loop running in separate thread."""
        try:
            while self.running:
                if UNIX_AVAILABLE and sys.stdin.isatty():
                    self._handle_raw_input()
                else:
                    self._handle_line_input()
        except Exception as e:
            # Restore terminal on error
            if UNIX_AVAILABLE and self.old_settings and sys.stdin.isatty():
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
            raise e
    
    def _handle_raw_input(self) -> None:
        """Handle character-by-character input for interactive terminals."""
        try:
            # Set terminal to raw mode
            if UNIX_AVAILABLE:
                tty.setraw(sys.stdin.fileno())
            
            while self.running:
                # Check if input is available
                if UNIX_AVAILABLE and select.select([sys.stdin], [], [], 0.1)[0]:
                    char = sys.stdin.read(1)
                    
                    if not char:
                        break
                    
                    # Handle special characters
                    if ord(char) == 3:  # Ctrl+C
                        self.input_callback("/quit")
                        break
                    elif ord(char) == 8:  # Ctrl+H - Help
                        self.input_callback("/help")
                    elif ord(char) == 12:  # Ctrl+L - Clear
                        self.input_callback("/clear")
                    elif ord(char) == 13 or ord(char) == 10:  # Enter
                        if self.current_line.strip():
                            self.input_callback(self.current_line.strip())
                            self.current_line = ""
                    elif ord(char) == 127 or ord(char) == 8:  # Backspace
                        if self.current_line:
                            self.current_line = self.current_line[:-1]
                    elif ord(char) >= 32:  # Printable characters
                        self.current_line += char
                        
        finally:
            # Restore terminal settings
            if UNIX_AVAILABLE and self.old_settings:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
    
    def _handle_line_input(self) -> None:
        """Handle line-based input for non-interactive terminals."""
        try:
            while self.running:
                line = input()
                if line is not None:
                    self.input_callback(line.strip())
        except EOFError:
            self.input_callback("/quit")
        except KeyboardInterrupt:
            self.input_callback("/quit")
    
    def get_current_input(self) -> str:
        """Get the current input line being typed."""
        return self.current_line

class SimpleInputHandler:
    """Simplified input handler for environments where raw input isn't available."""
    
    def __init__(self, input_callback: Callable[[str], None]):
        self.input_callback = input_callback
        self.running = False
        self.input_thread = None
    
    def start(self) -> None:
        """Start the input handler."""
        self.running = True
        self.input_thread = threading.Thread(target=self._input_loop, daemon=True)
        self.input_thread.start()
    
    def stop(self) -> None:
        """Stop the input handler."""
        self.running = False
        if self.input_thread and self.input_thread.is_alive():
            self.input_thread.join(timeout=1.0)
    
    def _input_loop(self) -> None:
        """Simple line-based input loop."""
        try:
            while self.running:
                try:
                    line = input()
                    if self.running and line is not None:
                        self.input_callback(line.strip())
                except EOFError:
                    break
                except KeyboardInterrupt:
                    self.input_callback("/quit")
                    break
        except Exception:
            pass
    
    def get_current_input(self) -> str:
        """Get current input (always empty for line-based input)."""
        return ""

def create_input_handler(input_callback: Callable[[str], None], use_raw_input: bool = True):
    """Factory function to create appropriate input handler."""
    if use_raw_input and UNIX_AVAILABLE and sys.stdin.isatty():
        try:
            return AsyncInputHandler(input_callback)
        except (ImportError, AttributeError):
            # Fall back to simple handler if termios not available
            return SimpleInputHandler(input_callback)
    else:
        return SimpleInputHandler(input_callback)