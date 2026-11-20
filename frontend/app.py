import os
import requests
import streamlit as st

st.set_page_config(page_title='Doc Code RAG · Documentation interne', page_icon='📚', layout='wide')
API = os.getenv('API_URL', 'http://localhost:8000')

def request(method, path, **kwargs):
    headers = {'Authorization': 'Bearer '+st.session_state['token']} if st.session_state.get('token') else {}
    try:
        timeout = int(os.getenv('CHAT_REQUEST_TIMEOUT', '1020')) if path == '/chat' else 240
        response = requests.request(method, API+path, headers=headers, timeout=timeout, **kwargs)
    except requests.RequestException:
        st.error('Le service est indisponible. Vérifiez le démarrage des conteneurs.')
        return None
    if response.status_code == 401 and path != '/auth/login':
        st.session_state.clear()
        st.rerun()
    if not response.ok:
        try:
            detail = response.json().get('detail','Erreur du service')
        except ValueError:
            detail = 'Erreur du service'
        st.error(detail if isinstance(detail,str) else 'Vérifiez les valeurs saisies.')
        return None
    return response.json()

st.title('Doc Code RAG')
st.caption('Votre documentation interne, des réponses vérifiables.')

if not st.session_state.get('token'):
    left, center, right = st.columns([1,2,1])
    with center:
        st.subheader('Connexion à votre espace')
        st.write('Posez vos questions en français ou en anglais. Chaque réponse s’appuie sur les documents auxquels vous avez accès.')
        with st.form('login'):
            email = st.text_input('Adresse e-mail')
            password = st.text_input('Mot de passe', type='password')
            submit = st.form_submit_button('Se connecter', use_container_width=True)
        if submit:
            result = request('POST','/auth/login',json={'email':email,'password':password})
            if result:
                st.session_state.update(token=result['access_token'],role=result['role'])
                st.rerun()
    st.stop()

with st.sidebar:
    st.subheader('Espace documentaire')
    st.caption('Rôle : '+st.session_state['role'])
    pages = ['Questions', 'Documents']
    if st.session_state['role'] == 'admin':
        pages.append('Administration')
        pages.append('Configuration LLM')
    page = st.radio('Navigation', pages)
    st.divider()
    st.caption('Les questions sont indépendantes. Les réponses précédentes ne sont pas utilisées.')
    if st.button('Se déconnecter', use_container_width=True):
        st.session_state.clear()
        st.rerun()

collections = request('GET','/collections')
if collections is None:
    st.stop()

if page == 'Questions':
    st.subheader('Que souhaitez-vous retrouver ?')
    st.caption(f'{len(collections)} collection(s) accessible(s) · Français / English')
    st.caption('La recherche locale sur CPU peut prendre plusieurs minutes, notamment pendant l’indexation de documents.')
    if not collections:
        st.info('Aucune collection accessible. Un administrateur peut vous attribuer un accès.')
    question = st.chat_input('Ex. Quelle est la procédure de déploiement ?', max_chars=2000)
    if question:
        with st.chat_message('user'):
            st.write(question)
        with st.spinner('Recherche dans vos documents…'):
            result = request('POST','/chat',json={'question':question})
        if result:
            with st.chat_message('assistant'):
                # Plain text prevents internal document text from causing remote image loads.
                st.text(result['answer'])
            if result['sources']:
                st.subheader('Vérifier les sources')
            for source in result['sources']:
                with st.expander(f"[{source['n']}] {source['document']}"):
                    st.text(source['section'] or '')
                    if source['page']:
                        st.caption(f"Page {source['page']}")
                    if source['lines']:
                        st.caption('Lignes '+source['lines'])
                    st.text(source['excerpt'])

elif page == 'Documents':
    st.subheader('Votre bibliothèque')
    if st.session_state['role'] in ('admin','manager'):
        with st.expander('Créer une collection'):
            with st.form('collection'):
                name = st.text_input('Nom de la collection', max_chars=160)
                create = st.form_submit_button('Créer')
            if create and request('POST','/collections',json={'name':name}):
                st.rerun()
    if not collections:
        st.info('Créez une collection ou demandez un accès à votre administrateur.')
        st.stop()
    collection = st.selectbox('Collection',collections,format_func=lambda c:c['name'])
    cid = collection['id']
    if collection['can_write']:
        upload, github = st.tabs(['Déposer un fichier', 'Connecter GitHub'])
        with upload:
            st.caption('PDF texte, DOCX, Markdown ou TXT · 20 Mo maximum')
            with st.form('upload',clear_on_submit=True):
                file = st.file_uploader('Document',type=['pdf','docx','md','txt','png','jpg','jpeg'])
                st.caption('OCR français/anglais pour les images et les pages PDF sans texte sélectionnable. Les scans prennent plus de temps à indexer.')
                send = st.form_submit_button('Indexer le document')
            if send and file:
                if request('POST',f'/collections/{cid}/documents',files={'file':(file.name,file.getvalue(),file.type)}):
                    st.success('Document reçu. L’indexation se poursuit en arrière-plan.')
        with github:
            st.caption('Une collection vide est requise. Les droits GitHub ne sont pas importés.')
            with st.form('github'):
                url = st.text_input('URL du dépôt',placeholder='https://github.com/organisation/depot')
                connect = st.form_submit_button('Connecter et indexer')
            if connect and request('POST',f'/collections/{cid}/github',json={'url':url}):
                st.success('Dépôt ajouté à la file d’indexation.')
    st.button('Actualiser les statuts')
    docs = request('GET',f'/collections/{cid}/documents')
    if docs == []:
        st.info('Cette collection ne contient aucun document.')
    for doc in docs or []:
        with st.container(border=True):
            a,b = st.columns([5,1])
            a.text(doc['name'])
            a.caption({'pending':'En attente','processing':'Indexation en cours','ready':'Prêt','failed':'Échec'}[doc['status']])
            if doc['error']:
                a.error(doc['error'])
            if collection['can_write']:
                with b.popover('Supprimer'):
                    st.write('Supprimer ce document et ses passages indexés ?')
                    if st.button('Confirmer',key=doc['id']):
                        if request('DELETE',f"/documents/{doc['id']}"):
                            st.rerun()

elif page == 'Configuration LLM':
    st.subheader('Connexion au LLM externe')
    st.write('La question et les extraits documentaires sélectionnés sont envoyés au fournisseur configuré. Les embeddings restent locaux.')
    st.caption('API compatible Chat Completions : URL de base HTTPS, authentification Bearer, réponses texte. Configuration partagée pour tous les utilisateurs.')
    settings = request('GET', '/admin/llm')
    if settings is None:
        st.stop()
    if st.session_state.pop('llm_saved', False):
        st.session_state['llm_api_key'] = ''
        st.success('Configuration enregistrée. Elle sera utilisée dès la prochaine question.')
    if settings.get('configured'):
        st.info(f"Configuration active : {settings['provider']} · {settings['model']} · clé enregistrée")
    else:
        st.info('Aucun fournisseur configuré.')
    with st.form('llm_settings', clear_on_submit=True):
        provider = st.text_input('Fournisseur', value=settings.get('provider', ''), placeholder='Ex. Mistral', max_chars=80)
        base_url = st.text_input('URL de base de l’API', value=settings.get('base_url', ''), placeholder='https://api.mistral.ai/v1', max_chars=500)
        model = st.text_input('Identifiant du modèle', value=settings.get('model', ''), placeholder='Identifiant fourni par votre fournisseur', max_chars=200)
        api_key = st.text_input('Clé API', type='password', max_chars=4096, key='llm_api_key',
            help='Laisser vide pour conserver la clé actuelle. Une nouvelle clé est obligatoire si le fournisseur ou l’URL change.')
        save = st.form_submit_button('Enregistrer la configuration')
    if save:
        result = request('PUT', '/admin/llm', json={'provider': provider, 'base_url': base_url,
                                                  'model': model, 'api_key': api_key or None})
        if result:
            st.session_state['llm_saved'] = True
            st.rerun()
    st.caption('Le test utilise la configuration enregistrée et envoie uniquement « Reply with OK. ». Il peut consommer quelques tokens.')
    if st.button('Tester la connexion enregistrée', disabled=not settings.get('configured')):
        with st.spinner('Test du fournisseur…'):
            if request('POST', '/admin/llm/test'):
                st.success('Le fournisseur et le modèle répondent correctement.')
    if settings.get('configured'):
        with st.popover('Supprimer la connexion'):
            st.write('Supprimer la configuration et sa clé API de la base ? La génération sera indisponible jusqu’à une nouvelle configuration.')
            if st.button('Confirmer la suppression de la connexion'):
                if request('DELETE', '/admin/llm'):
                    st.rerun()

else:
    st.subheader('Administration des accès')
    users, permissions = st.tabs(['Créer un utilisateur','Droits des collections'])
    with users:
        with st.form('user'):
            email = st.text_input('E-mail')
            password = st.text_input('Mot de passe initial (12 caractères minimum)',type='password')
            role = st.selectbox('Rôle',['developer','manager','admin'])
            submit = st.form_submit_button('Créer l’utilisateur')
        if submit and request('POST','/admin/users',json={'email':email,'password':password,'role':role}):
            st.success('Utilisateur créé.')
    with permissions:
        if not collections:
            st.info('Créez d’abord une collection dans Documents.')
        else:
            selected = st.selectbox('Collection à gérer',collections,format_func=lambda c:c['name'])
            current = request('GET','/admin/permissions') or []
            st.dataframe([{'Rôle':p['role'],'Accès':'Lecture et écriture' if p['can_write'] else 'Lecture'}
                          for p in current if p['collection_id']==selected['id']],hide_index=True,use_container_width=True)
            with st.form('permission'):
                role = st.selectbox('Rôle à modifier',['developer','manager'])
                write = st.checkbox('Autoriser le dépôt et la suppression')
                grant = st.form_submit_button('Attribuer / modifier')
                revoke = st.form_submit_button('Révoquer l’accès')
            path = f"/admin/roles/{role}/collections/{selected['id']}"
            if grant and request('PUT',path,json={'can_write':write}):
                st.rerun()
            if revoke and request('DELETE',path):
                st.rerun()
