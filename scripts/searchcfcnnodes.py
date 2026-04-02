def check():
    # ... other code ...
    finally:
        # Removed duplicate global checked declaration
        pass

def async_query_middle():
    global middle
    # ... other code ...

# ... other code ...

def show_progress():
    print('Progressing...', flush=True)
