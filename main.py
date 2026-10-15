# main.py
# Terminal interface for Banking AI Agent

from src.agent.loop import process_message, confirm_action


def show_banner():
    print("\n" + "═" * 60)
    print("  🏦 Banking AI Agent")
    print("═" * 60)
    print("  Type 'help' to see commands")
    print("  Type 'exit' to quit")
    print("═" * 60)


def main():
    show_banner()
    
    last_intent = None  # Store intent waiting for confirmation
    
    while True:
        try:
            # ─── Get input ───
            user_input = input("\nYou: ").strip()
            
            if not user_input:
                continue
            
            # ─── Exit ───
            if user_input.lower() in ["exit", "quit", "q"]:
                print("\nAI:  Goodbye 👋\n")
                break
            
            # ─── Answer confirmation (y/n) ───
            if last_intent:
                if user_input.lower() in ["y", "yes"]:
                    response = confirm_action(last_intent)
                    last_intent = None
                    print(f"\nAI:  {response['reply']}")
                    continue
                elif user_input.lower() in ["n", "no"]:
                    last_intent = None
                    print("\nAI:  ❌ Cancelled")
                    continue
            
            # ─── Process message ───
            response = process_message(user_input)
            print(f"\nAI:  {response['reply']}")
            
            # ─── Store intent if pending confirmation ───
            if response.get("requires_confirmation"):
                last_intent = response.get("intent")
            
            # ─── Handle MFA (not implemented yet) ───
            elif response.get("requires_mfa"):
                print("     (MFA not implemented yet — skipping)")
        
        except KeyboardInterrupt:
            print("\n\nAI:  Goodbye 👋\n")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()