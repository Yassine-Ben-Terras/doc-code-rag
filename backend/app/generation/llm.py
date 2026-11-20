import httpx
from app.core.db import transaction
from app.generation.prompt import SYSTEM
from app.generation.settings import LLMError, read_settings, decrypt_key

def complete(settings, prompt, *, probe=False):
    key = decrypt_key(settings)
    try:
        with httpx.Client(timeout=180, trust_env=False, follow_redirects=False) as client:
            response = client.post(settings['base_url']+'/chat/completions',
                headers={'Authorization': 'Bearer '+key}, json={
                    'model': settings['model'], 'stream': False,
                    'messages': [
                        {'role': 'system', 'content': 'Reply briefly.' if probe else SYSTEM},
                        {'role': 'user', 'content': prompt}],
                    # Reasoning models share this budget between reasoning and final text.
                    'max_tokens': 4096})
            response.raise_for_status()
            choice = response.json()['choices'][0]
            if choice.get('finish_reason') == 'length':
                raise LLMError('Le modèle a atteint la limite de génération avant de terminer sa réponse. Réessayez avec une question plus courte ou un modèle moins gourmand en raisonnement.')
            answer = choice['message'].get('content')
            if not isinstance(answer, str) or not answer.strip():
                # Reasoning is not a final answer and must never be used as one.
                raise LLMError('Le fournisseur a répondu sans réponse finale exploitable. Le modèle peut avoir consommé son budget en raisonnement ; essayez un autre modèle ou réessayez.')
            return answer.strip()
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code in (401, 403):
            message = 'Le fournisseur refuse l’accès : vérifier la clé API et les droits du modèle.'
        elif code == 429:
            message = 'Quota ou limite de débit du fournisseur atteint.'
        else:
            message = 'Le fournisseur a refusé la requête : vérifier l’URL, le modèle et sa compatibilité Chat Completions.'
        raise LLMError(message) from None
    except httpx.TimeoutException:
        raise LLMError('Le fournisseur met trop de temps à répondre (délai de 180 secondes). Réessayez.') from None
    except httpx.RequestError:
        raise LLMError('Connexion au fournisseur impossible. Vérifier le réseau et l’URL de l’API.') from None
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise LLMError('Fournisseur indisponible ou réponse incompatible avec Chat Completions.') from None

def generate(prompt):
    with transaction() as db:
        settings = read_settings(db)
    if not settings:
        raise LLMError('Aucun LLM configuré. Un administrateur doit configurer le fournisseur dans Configuration LLM.')
    return complete(settings, prompt)
