"""Servicos de dominio.

Services expoem funcoes sincronas e sem Qt. A responsabilidade de rodar em
thread/worker fica com a camada de UI.

Regras importantes:

- Nada de QObject, Signal, QThread ou QRunnable.
- Para notificacoes, usar callbacks simples (Callable) ou retornos
  estruturados.
- Textos de mensagem de usuario ficam na UI. Aqui se levanta excecoes do
  core.exceptions com dados estruturados.
"""
