"""
Final fixes for mini_player.py
"""
import os
from pathlib import Path

def fix_mini_player():
    # Read the mini_player file
    mini_player_path = Path("src/mmst/plugins/media_library/enhanced/mini_player.py")
    
    if not mini_player_path.exists():
        print(f"Cannot find {mini_player_path}")
        return
        
    with open(mini_player_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # In the fallback implementation we need to make sure that the root is accessible outside __init__
    new_content = content.replace("            root = QHBoxLayout(self._widget_parent)  # type: ignore", 
                                  "            self.root = QHBoxLayout(self._widget_parent)  # type: ignore")
    new_content = new_content.replace("            root = QHBoxLayout()  # type: ignore", 
                                  "            self.root = QHBoxLayout()  # type: ignore")
    
    # Make it use self.root not root for root.addWidget
    new_content = new_content.replace("        root.addWidget(self.prev_btn)  # type: ignore", 
                                      "        try: self.root.addWidget(self.prev_btn)  # type: ignore\n        except Exception: pass")
    new_content = new_content.replace("        root.addWidget(self.play_btn)  # type: ignore", 
                                      "        try: self.root.addWidget(self.play_btn)  # type: ignore\n        except Exception: pass")
    new_content = new_content.replace("        root.addWidget(self.next_btn)  # type: ignore", 
                                      "        try: self.root.addWidget(self.next_btn)  # type: ignore\n        except Exception: pass")
    new_content = new_content.replace("        root.addWidget(self.title_lbl)  # type: ignore", 
                                      "        try: self.root.addWidget(self.title_lbl)  # type: ignore\n        except Exception: pass")
    new_content = new_content.replace("        root.addWidget(self.slider, 1)  # type: ignore", 
                                      "        try: self.root.addWidget(self.slider, 1)  # type: ignore\n        except Exception: pass")
    
    # Write the fixed file
    with open(mini_player_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    
    print(f"Updated {mini_player_path}")

if __name__ == "__main__":
    fix_mini_player()