import subprocess
import sys
import time
import shutil

CLUSTER_NAME = "main-cluster"
NAMESPACE = "monitoring-app"
IMAGE_NAME = "python-metrics-app"
K8S_MANIFESTS_PATH = "k8s/"

def check_prerequisites():
    """Checks if all required command-line tools are installed."""
    print("--- 0. Checking Prerequisites ---")
    required_tools = ["docker", "k3d", "kubectl"]
    for tool in required_tools:
        if not shutil.which(tool):
            print(f"❌ Error: Required tool '{tool}' is not installed or not in your PATH.")
            sys.exit(1)
    print("✅ All prerequisites are satisfied.")

def run_command(command_args, stream_output=True, check=True):
    """
    Executes a shell command, streams its output, and handles errors.
    
    Args:
        command_args: A list of strings representing the command and its arguments.
        stream_output: If True, streams the command's stdout.
        check: If True, exits the script if the command fails.
        
    Returns:
        The command's exit code.
    """
    print(f"\n🚀 Executing: {' '.join(command_args)}")
    try:
        if stream_output:
            process = subprocess.Popen(
                command_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )
            for line in process.stdout:
                print(line, end='')
            process.wait()
            if check and process.returncode != 0:
                print(f"\n❌ Command failed with exit code {process.returncode}")
                sys.exit(process.returncode)
            return process.returncode
        else:
            result = subprocess.run(command_args, capture_output=True, text=True)
            if check and result.returncode != 0:
                print(f"\n❌ Command failed with exit code {result.returncode}")
                print(f"Stderr: {result.stderr.strip()}")
                sys.exit(result.returncode)
            return result.returncode
    except FileNotFoundError:
        print(f"❌ Error: Command '{command_args[0]}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
        sys.exit(1)

def create_k3d_cluster():
    """Creates a k3d cluster if it doesn't already exist."""
    print("\n--- 1. Creating k3d Cluster ---")
    if run_command(["k3d", "cluster", "get", CLUSTER_NAME], stream_output=False, check=False) == 0:
        print(f"✅ Cluster '{CLUSTER_NAME}' already exists. Skipping creation.")
        return

    print(f"Cluster '{CLUSTER_NAME}' not found. Creating it now...")
    create_command = ["k3d", "cluster", "create", CLUSTER_NAME]
    run_command(create_command)
    print(f"✅ Cluster '{CLUSTER_NAME}' created.")

def import_image_to_cluster():
    """Imports the local Docker image directly into the k3d cluster nodes."""
    print("\n--- 2. Importing Docker Image into k3d Cluster ---")
    import_command = ["k3d", "image", "import", f"{IMAGE_NAME}:latest", "-c", CLUSTER_NAME]
    run_command(import_command)

def deploy_monitoring_stack():
    """Deploys the kube-prometheus-stack using Helm."""
    print("\n--- 4. Deploying Monitoring Stack (Prometheus & Grafana) ---")
    
    print("Adding Prometheus Helm repository...")
    run_command(["helm", "repo", "add", "prometheus-community", "https://prometheus-community.github.io/helm-charts"], check=False)
    
    print("Updating Helm repositories...")
    run_command(["helm", "repo", "update"])
    
    print("Installing or upgrading kube-prometheus-stack...")
    # This command is idempotent. It will install if not present, or upgrade if it is.
    # We also need to tell Prometheus to look for ServiceMonitors with the label 'release: prometheus'
    helm_install_command = [
        "helm", "upgrade", "--install", "prometheus", "prometheus-community/kube-prometheus-stack",
        "--namespace", NAMESPACE,
        "--set", "prometheus.prometheusSpec.serviceMonitorSelector.matchLabels.release=prometheus"
    ]
    run_command(helm_install_command)
    print("✅ Monitoring stack deployed successfully.")
    
def deploy_application():
    """Creates a namespace and applies Kubernetes manifests to deploy the app."""
    print("\n--- 3. Deploying Application to Kubernetes ---")
    
    print(f"Creating namespace '{NAMESPACE}' if it doesn't exist...")
    if run_command(["kubectl", "get", "namespace", NAMESPACE], stream_output=False, check=False) != 0:
        run_command(["kubectl", "create", "namespace", NAMESPACE])
        print(f"✅ Namespace '{NAMESPACE}' created.")
    else:
        print(f"✅ Namespace '{NAMESPACE}' already exists.")

    print(f"Applying Kubernetes manifests from '{K8S_MANIFESTS_PATH}'...")
    run_command(["kubectl", "apply", "-f", K8S_MANIFESTS_PATH, "-n", NAMESPACE])
    print("✅ Application deployed successfully.")

def cleanup():
    """Deletes the k3d cluster and associated resources."""
    print("\n--- Cleaning up environment ---")
    print(f"Deleting k3d cluster '{CLUSTER_NAME}'...")
    run_command(["k3d", "cluster", "delete", CLUSTER_NAME], check=False)
    print("✅ Cleanup complete.")

def main():
    """Main function to parse arguments and run the deployment or cleanup steps."""
    start_time = time.time()
    
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'cleanup':
        cleanup()
    else:
        try:
            check_prerequisites()
            create_k3d_cluster()
            import_image_to_cluster()
            deploy_monitoring_stack()
            deploy_application()
            print("\n🎉 Deployment script finished successfully! 🎉")
            print("To clean up the environment, run: python deploy.py cleanup")
        except SystemExit as e:
            print(f"\nScript exited with code {e.code}")
        except Exception as e:
            print(f"\nAn unexpected error occurred: {e}")

    end_time = time.time()
    print(f"Total execution time: {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    main() 