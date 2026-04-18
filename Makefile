.PHONY: minikube-images minikube-deploy minikube-up minikube-delete minikube-status

minikube-images:
	minikube image build -t langgraph-backend:latest ./backend
	minikube image build -t langgraph-frontend:latest ./frontend

minikube-deploy:
	kubectl apply -f k8s/

minikube-up: minikube-images minikube-deploy

minikube-delete:
	kubectl delete -f k8s/

minikube-status:
	kubectl get pods -o wide
