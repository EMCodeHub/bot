from pathlib import Path
import difflib
original = Path('tmp/original_chat.py').read_text(encoding='utf-8')
current = Path('src/backend/app/routes/chat.py').read_text(encoding='utf-8')
diff = difflib.unified_diff(original.splitlines(keepends=True), current.splitlines(keepends=True), fromfile='a/src/backend/app/routes/chat.py', tofile='b/src/backend/app/routes/chat.py')
print(''.join(diff))
