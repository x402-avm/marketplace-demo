import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common.paid import serve
from proxy import mcp
if __name__ == "__main__":
    serve(mcp, "image_edit_mcp", 3)
