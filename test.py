import sys
print(sys.version)
try:
    import fastapi
    print("fastapi ok")
except ImportError:
    print("fastapi missing")
