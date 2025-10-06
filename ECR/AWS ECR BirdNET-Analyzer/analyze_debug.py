from birdnet_analyzer.analyze.core import analyze
import sys

def main():
    args = {
        "audio_input": sys.argv[1],
        "output": "/app/output",
        "lat": 13.75,
        "lon": 100.50,
        "rtype": "csv",
        "locale": "en"
    }
    try:
        analyze(**args)
    except Exception as e:
        print("Error occurred during analysis:")
        print(e)

if __name__ == "__main__":
    main()
