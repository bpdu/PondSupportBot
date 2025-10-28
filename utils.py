def load_prompt(name):
    with open(f"resources/{name}.txt", "r", encoding="utf8") as file:
        return file.read()

