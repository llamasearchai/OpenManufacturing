import os
import sys
# Adjust sys.path if running this script directly from project root
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from openmanufacturing.core.process.workflow_manager import WorkflowManager # Assuming SomeClass is WorkflowManager or similar

def main():
    print("Script running")
    # Example: workflow_manager = WorkflowManager()
    # print(workflow_manager)

if __name__ == "__main__":
    main()