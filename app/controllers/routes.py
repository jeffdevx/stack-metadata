#import flask app
from app import app, mail
#import dos metodos do flask
from flask import request, render_template, url_for, redirect, flash, abort
#import do objeto do banco de dados
from app import database
#import das coleções do banco de dados
from app.models.learning_object import LearningObject
from app.models.site import Site
from app.models.user import User
#import dos formulários
from app.models.forms import LoginForm, RegisterForm, ProfileForm, ForgotPasswordForm, VerifyCodeForgotPasswordForm, ChangePasswordForm
#import do contralador de seção do usuário e verificação de senha
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
#import do controller da api do stackexchange
from app.controllers.api_stackexchange import StackExchange
#import message para envio do email
from flask_mail import Message
#import do gerador de hash base64
import secrets
#outros imports
import datetime
import pytz
import random


#### CACHE DA APLICAÇÃO ####

#Lista para gestão do cache antes do login do usuário
cache_app_before_login = []

#Lista para gestão do cache depois do login do usuário
cache_app_after_login = []

#### ROTAS DA APLICAÇÃO ####

#### Tela principal do sistema ####

@app.route("/")
@app.route("/index/")
@login_required
def index():
    try:
        number_sites = len(database.list("sites"))
    except:
        number_sites = 0
        
    try:
        number_learning_objects = len(database.list("learning_objects"))
    except:
        number_learning_objects = 0
    return render_template("index.html", number_sites=number_sites, number_learning_objects=number_learning_objects)

#### Pesquisa e Atulização dos sites disponiveis para a busca na api ####

#Pesquisa/atualização de sites disponiveis para busca na api
@app.route("/search_sites/", methods=['GET'])
@login_required
def search_sites():
    sites_database = database.list("sites")
    stackexchange = StackExchange(100, None)
    pages_sites = stackexchange.sites()
    if sites_database:
        for page in pages_sites:
            for site in page["items"]:
                site_object = Site(site)
                site_json = site_object.get_as_json()
                for site_database in sites_database:
                    if site_json["site"]["api_parameter"] == site_database["site"]["api_parameter"]:
                        #site_update = {**site_database, **site_json}
                        site_update = site_json
                        database.update("sites", site_database, site_update)       
                        break
                if site_update == None or "":
                    database.create("sites", site_object)
                    break
    else:
        for page in pages_sites:
            for site in page["items"]:
                try:
                    site_object = Site(site)
                    database.create("sites", site_object)
                except:
                    continue
    return redirect(url_for('view_sites'))

#Visualização dos sites
@app.route("/view_sites/", methods=['GET'])
@login_required
def view_sites():
    sites = database.list("sites")
    list_sites = []
    for site in sites:
        list_sites.append(site["site"])
    return render_template("view_sites.html", sites=list_sites)


#### Pesquisa e CRUD de objetos de aprendizagens ####

#Pesquisa de objetos de aprendizagens na api
@app.route("/search_api/", methods=['GET'])
@login_required
def search_api():
    sites = database.list("sites")
    #global list_sites
    list_sites = []
    for site in sites:
        list_sites.append(site["site"])
    return render_template("search_api.html", sites=list_sites)

#Apresenta os resultados da pesquisa na api
@app.route("/results_search_api/", methods=['POST'])
@login_required
def results_search_api():   
    global cache_app_after_login
    stackexchange = StackExchange(30, 1)
    sites = database.list("sites")
    list_sites_api = []
    list_results = []
    
    #pegar as datas
    date_start = datetime.datetime.strptime(request.form.get('date_start')[:10], "%d/%m/%Y").replace(tzinfo=pytz.utc).timestamp() #para pegar somente a data
    date_end = datetime.datetime.strptime(request.form.get('date_end')[:10], "%d/%m/%Y").replace(tzinfo=pytz.utc).timestamp() #para pegar somente a data
    #pegar as ordenações
    selected_sort = request.form.get('selected-sort')
    selected_order = request.form.get('selected-order')
    #pegar as tags e não tags
    selected_tagged = request.form.get('selected-tagged')
    selected_nottagged = request.form.get('selected-nottagged')
    #pegar os sites
    selected_sites = request.form.getlist('selected-sites')
    #pegar seleção de somente perguntas aceitas
    accepted = request.form.get('accepted')
    #pegar o tipo da busca
    selected_type_search = request.form.getlist('selected-type-search') 
    #pegar a busca
    search = request.form.get('search')
    #date_format = ciso8601.parse_datetime(str(date_start))
    # to get time in seconds:
    #print(time.mktime(date_format.timetuple()))
    """print(date_start)
    print(date_end)
    print(selected_sort)
    print(selected_order)
    print(selected_tagged)
    print(selected_nottagged)
    print(selected_type_search[0])
    print(accepted)"""
    
    if selected_sites:
        for option in selected_sites:
            option = option.split("-")[1]
            for site in sites:
                if option == site["site"]["api_parameter"]:
                    list_sites_api.append(site["site"])
                    break
    for site in list_sites_api:
        #list_result_items = stackexchange.search_advanced(str(search), str(site["api_parameter"]))
        list_result_items = stackexchange.search_advanced(str(search), str(site["api_parameter"]), date_start, date_end, str(selected_sort), str(selected_order), accepted, selected_tagged, selected_nottagged, str(selected_type_search[0]))
        list_results.append(list_result_items)
    
    update_results = []
    update = []
    for results, site in zip(list_results, list_sites_api):
        for result in results:
            item_db = database.filter_by('learning_objects', {"general.identifier": result["question_id"]})
            if item_db:
                update.append(1)
            else:
                update.append(0)
        update_results.append(update)
        update = []
    
    cache_user = []
    for x in range(len(cache_app_after_login)):
        if current_user.email == cache_app_after_login[x][0]:              
            cache_user = cache_app_after_login[x]
            break        
    if cache_user:
        cache_user[1] = list_results
        cache_user[2] = list_sites_api
        cache_user[3] = update_results
    else:
        cache_user.append(current_user.email)
        cache_user.append(list_results)
        cache_user.append(list_sites_api)
        cache_user.append(update_results)
        cache_app_after_login.append(cache_user)
    
    return render_template("results_search_api.html", list_results=cache_user[1], list_sites_api=cache_user[2], update_results=cache_user[3])

#Cria um novo objeto de aprendizagem a partir da pesquisa retornada na api
@app.route("/create_learning_object/<int:index_list_results>/<int:index_result>/<string:name_site>/<string:api_site>")
@login_required
def create_learning_object(index_list_results, index_result, name_site, api_site):
    list_results = []
    list_sites_api = []
    update_results = []
    cache_user = []
    global cache_app_after_login
    user = None
    for x in range(len(cache_app_after_login)):
        if current_user.email == cache_app_after_login[x][0]:              
            cache_user = cache_app_after_login[x]
            user = x
            break  
    if cache_user:                                
        list_results = cache_user[1]
        list_sites_api = cache_user[2]
        update_results = cache_user[3]       
    save_item = list_results[index_list_results][index_result]
    #verificar se já esta no banco de dados e impedir de incluir novamente
    learning_object = LearningObject(save_item, name_site, api_site)
    learning_object_json = learning_object.get_as_json()
    item_db = database.filter_by('learning_objects', {"general.identifier": learning_object_json['general']['identifier'][1]})
    if not item_db:
        print("create")
        database.create("learning_objects", learning_object)
        update_results[index_list_results][index_result] = 1
        cache_user[3] = update_results
        cache_app_after_login[user] = cache_user
        return render_template("results_search_api.html", list_results=list_results, list_sites_api=list_sites_api, update_results=update_results)
    else:
        print("update")
        database.update("learning_objects", item_db[0])
        return render_template("results_search_api.html", list_results=list_results, list_sites_api=list_sites_api, update_results=update_results)

#Pesquisa de objetos de aprendizagens no banco de dados
@app.route("/search_database/")
def search_database():
    sites = database.list("sites")
    list_sites = []
    for site in sites:
        list_sites.append(site["site"])
    return render_template("search_database.html", sites=list_sites)

#Apresenta os resultados da pesquisa no banco de dados
@app.route("/results_search_database/")
def results_search_database():
    date_start = datetime.datetime.strptime(request.form.get('date_start')[:10], "%d/%m/%Y").replace(tzinfo=pytz.utc).timestamp() #para pegar somente a data
    date_end = datetime.datetime.strptime(request.form.get('date_end')[:10], "%d/%m/%Y").replace(tzinfo=pytz.utc).timestamp() #para pegar somente a data
    #pegar as ordenações
    selected_sort = request.form.get('selected-sort')
    selected_order = request.form.get('selected-order')
    #pegar as tags e não tags
    selected_tagged = request.form.get('selected-tagged')
    selected_nottagged = request.form.get('selected-nottagged')
    #pegar os sites
    selected_sites = request.form.getlist('selected-sites')
    #pegar seleção de somente perguntas aceitas
    accepted = request.form.get('accepted')
    #pegar o tipo da busca
    selected_type_search = request.form.getlist('selected-type-search') 
    #pegar a busca
    search = request.form.get('search')
    pass

#Visualiza os objetos de aprendizagens que estão no banco de dados
@login_required
@app.route("/view_learning_objects/")
def view_learning_objects():
    learning_objects = database.list("learning_objects")
    list_learning_objects = []
    for learning_object in learning_objects:
        list_learning_objects.append(learning_object)
    return render_template("view_learning_objects.html", learning_objects=list_learning_objects)

#Visualiza o objeto de aprendizagem
@login_required
@app.route("/view_learning_object/<string:id_learning_object_0>/<int:id_learning_object_1>", methods=['GET', 'POST'])
def view_learning_object(id_learning_object_0, id_learning_object_1):
    learning_object = database.filter_by('learning_objects', {"general.identifier": id_learning_object_0,"general.identifier": id_learning_object_1})
    return render_template("view_learning_object.html", learning_object=learning_object[0])

#Edita o objeto de aprendizagem
@login_required
@app.route("/edit_learning_object/<string:id_learning_object_0>/<int:id_learning_object_1>", methods=['GET', 'POST'])
def edit_learning_object(id_learning_object_0, id_learning_object_1):
    learning_object = database.filter_by('learning_objects', {"general.identifier": id_learning_object_0,"general.identifier": id_learning_object_1})
    return render_template("edit_learning_object.html", learning_object=learning_object[0])

#Atualiza o objeto de aprendizagem que foi editado
@login_required
@app.route("/update_learning_object/<string:id_learning_object_0>/<int:id_learning_object_1>", methods=['GET', 'POST'])
def update_learning_object(id_learning_object_0, id_learning_object_1):
    save_edit_learning_object = request.get_json()
    if save_edit_learning_object:
        learning_object_db = database.filter_by('learning_objects', {"general.identifier": id_learning_object_0,"general.identifier": id_learning_object_1})
        database.update("learning_objects", learning_object_db[0], save_edit_learning_object)
        #print('\n',json.dumps(save_edit_learning_object, indent=2),'\n')
    return redirect(url_for("view_learning_objects"))

#Deleta o objeto de aprendizagem
@login_required
@app.route("/delete_learning_object/<string:id_learning_object_0>/<int:id_learning_object_1>")
def delete_learning_object(id_learning_object_0, id_learning_object_1):
    learning_object_db = database.filter_by('learning_objects', {"general.identifier": id_learning_object_0,"general.identifier": id_learning_object_1})
    database.delete("learning_objects", learning_object_db[0])
    return redirect(url_for("view_learning_objects"))


#### Login, Registro, Perfil, Logout e Recuperação de senha ####

#Registro de conta
@app.route("/register/", methods=['GET', 'POST'])
def register():
    if not current_user.is_authenticated:
        form = RegisterForm()
        if form.validate_on_submit():
            name = form.name.data
            email = form.email.data
            password = form.password.data
            query = database.filter_by('users', {"email": email})
            if not query:
                user = User(name, email, password)
                database.create("users", user)
                flash('Conta registrada com sucesso!', 'success')
                return redirect(url_for("login"))
            else:
                flash('Email já cadastrado', 'danger')
        return render_template('register.html', form=form)
    else:
        return redirect(url_for("index"))

#Login - Entrar no sistema
@app.route("/login/", methods=['GET', 'POST'])
def login():
    if not current_user.is_authenticated:
        form = LoginForm()
        if form.validate_on_submit():
            email = form.email.data
            password = form.password.data
            remember = form.remember.data
            query = database.filter_by('users', {"email": email})
            if query:
                user_bd = query[0]
                if check_password_hash(user_bd['password'], password):
                    user = User(user_bd['name'], user_bd['email'], user_bd['password'])
                    login_user(user, remember=remember)
                    flash('Login realizado com sucesso!', 'success')
                    return redirect(url_for("index"))
                else:
                    flash('Problema com o login. Por favor verifique seu email e senha.', 'danger')
        return render_template('login.html', form=form)
    else:
        return redirect(url_for("index"))

#Logout - Sair do sistema
@app.route("/logout/", methods=['GET', 'POST'])
@login_required
def logout():
    global cache_app_after_login
    for x in range(len(cache_app_after_login)):
        if current_user.email == cache_app_after_login[x][0]:              
            cache_app_after_login.pop(x)
            break
    logout_user()
    return redirect(url_for("login"))

#Perfil do usuário
@app.route("/profile/", methods=['GET', 'POST'])
@login_required
def profile():
    msg_dialog = None
    type_dialog = None
    form = ProfileForm()
    if form.validate_on_submit():
        name = form.name.data
        current_password = form.current_password.data
        new_password = form.new_password.data
        confirm_new_password = form.confirm_new_password.data
        #busca dados do usuário no banco
        query = database.filter_by('users', {"email": current_user.email})
        if query:
            user_bd = query[0]
            #verificar se a senha atual é igual a sanha no banco de dados
            if check_password_hash(user_bd['password'], current_password):       
                if new_password == confirm_new_password:
                    user_temp = User(name, current_user.email, new_password)
                    database.update("users", user_bd, user_temp.get_as_json())
                    msg_dialog = "Dados do perfil alterados com sucesso!"
                    type_dialog = "dafault"
                    form.name.data = name
                    return render_template('profile.html', form=form, msg_dialog=msg_dialog, type_dialog=type_dialog)
                else:
                    msg_dialog = "A confirmação de senha está incorreta!"
                    type_dialog = "danger"
                    return render_template('profile.html', form=form, msg_dialog=msg_dialog, type_dialog=type_dialog)
            else:
                msg_dialog = "A senha atual informada está incorreta!"
                type_dialog = "danger"
                return render_template('profile.html', form=form, msg_dialog=msg_dialog, type_dialog=type_dialog)
        else:
            abort(500)
    else:
        form.name.data = current_user.name
        return render_template('profile.html', form=form, msg_dialog=msg_dialog, type_dialog=type_dialog)

#Recuperação de senha
@app.route("/forgot_password/", methods=['GET', 'POST'])
def forgot_password():
    if not current_user.is_authenticated:
        global cache_app_before_login
        form = ForgotPasswordForm()
        if form.validate_on_submit():
            query = database.filter_by('users', {"email": form.email.data})
            if query:
                user_bd = query[0] 
                
                #gera codigo temporário para recuperar a senha
                number = range(0, 9)
                code_temp = ''
                for i in range(6):
                    code_temp += str(random.choice(number))
                
                #gerando hash de segurança do link de recuperação
                token_temp = secrets.token_hex(64)
                
                #gera validade do codigo e do token
                validate_temp = int(datetime.datetime.now().replace(tzinfo=pytz.utc).timestamp()+3600) #soma 3600 segundos ao tempo de validade para ser valido por 1 hora
                        
                #gestão do cache
                cache_user_temp = [] 
                for x in range(len(cache_app_before_login)):
                    if user_bd['email'] == cache_app_before_login[x][0]:              
                        cache_user_temp = cache_app_before_login[x]
                        break        
                if cache_user_temp:
                    cache_user_temp[0] = user_bd
                    cache_user_temp[1] = int(code_temp)
                    cache_user_temp[2] = str(token_temp)
                    cache_user_temp[3] = int(validate_temp)
                else:
                    cache_user_temp.append(user_bd)
                    cache_user_temp.append(int(code_temp))
                    cache_user_temp.append(str(token_temp))
                    cache_user_temp.append(int(validate_temp))
                    cache_app_before_login.append(cache_user_temp)
                
                #envio do email com o código
                msg = Message(
                    'Código para recuperação de senha!',
                    recipients=[form.email.data],
                )
                msg.html = f"""  
                    <div width="100%" style="margin:0;padding:0!important">
                        <center style="width:100%;>
                            <div style="max-width:600px;margin:0 auto" class="m_-2585479850499807075email-container">
                                <table width="100%" cellspacing="0" cellpadding="0" border="0" align="center">
                                    <tbody>
                                        <tr>
                                            <td height="20"></td>
                                        </tr>
                                        <tr>
                                            <td align="center">
                                                <p style="line-height:1.5;font-family:'Lato',Calibri,Arial,sans-serif;font-size:18px;color:#000000;text-align:center;text-decoration:none"> 
                                                    Para resuperar a sua senha use o código abaixo:
                                                </p>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                                <table style="border:1px solid #4400ff;margin-top:10px" border="0" width="200" cellspacing="0" cellpadding="0" align="center">
                                    <tbody>
                                        <tr>
                                            <td height="60">
                                                <p style="font-family:'Lato',Calibri,Arial,sans-serif;font-size:22px;color:#4400ff;text-align:center">
                                                    <strong>
                                                        {code_temp}
                                                    </strong>
                                                </p>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                                <table width="100%" cellspacing="0" cellpadding="0" border="0" align="center">
                                    <tbody>
                                        <tr>
                                            <td height="20"></td>
                                        </tr>
                                        <tr>
                                            <td align="center">
                                                <p style="line-height:1.5;font-family:'Lato',Calibri,Arial,sans-serif;font-size:12px;color:#000000;text-align:center;text-decoration:none"> 
                                                    Este código é válido por 1 hora.
                                                </p>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </center>
                        <div class="yj6qo"></div>
                        <div class="adL"></div>
                    </div>
                """
                mail.send(msg)
                return redirect(url_for("verify_code_forgot_password", token=token_temp))
            else:
                return redirect(url_for("register"))
        else:
            return render_template('forgot_password.html', form=form)
    else:
        return redirect(url_for("index"))
    
#Verifica código enviado da recuperação de senha
@app.route("/verify_code_forgot_password/<string:token>/", methods=['GET', 'POST'])
def verify_code_forgot_password(token):#verificar se codigo esta no cache e se esta dentro do tempo permitido, se não estiver lançar uma mensagem de errr dizendo que o codigo não existe ou expirou
    if not current_user.is_authenticated:
        global cache_app_before_login
        #verificando token e validade dele
        token_validate = False
        date_now = int(datetime.datetime.now().replace(tzinfo=pytz.utc).timestamp())
        for x in range(len(cache_app_before_login)):
            if token == cache_app_before_login[x][2]:
                if date_now < cache_app_before_login[x][3]: #verifica se o token passado no link é o mesmo que foi gerado pelo sistema e ainda está válido  
                    token_validate = True
                    break
                else:
                    cache_app_before_login.pop(x) #limpa o cache_app_before_login
                    break
        if token_validate:   
            form = VerifyCodeForgotPasswordForm()
            if form.validate_on_submit():
                verified_code = False            
                for x in range(len(cache_app_before_login)):
                    if form.code.data == cache_app_before_login[x][1]: #verifica se o codigo digitado é válido     
                        verified_code = True
                        break
                if verified_code:
                    token_verification_code = f"{token[:50]}{form.code.data}{token[50:]}" #concatena o token com o codigo enviado
                    return redirect(url_for("change_password", token_verification_code=token_verification_code))
                else:
                    return render_template('verify_code_forgot_password.html', form=form)
            else:
                return render_template('verify_code_forgot_password.html', form=form)
        else:    
            abort(404)
    else:
        return redirect(url_for("index"))

#Alteração de senha após as validações anteriores da recuperação de senha
@app.route("/change_password/<string:token_verification_code>/", methods=['GET', 'POST'])
def change_password(token_verification_code):
    if not current_user.is_authenticated:
        global cache_app_before_login
        token_validate = False        
        token = f"{token_verification_code[:50]}{token_verification_code[56:]}"
        date_now = int(datetime.datetime.now().replace(tzinfo=pytz.utc).timestamp())
        for x in range(len(cache_app_before_login)):
            if token == cache_app_before_login[x][2]:
                if date_now < cache_app_before_login[x][3]: #verifica se o token passado no link é o mesmo que foi gerado pelo sistema e ainda está válido  
                    token_validate = True
                    break
                else:
                    cache_app_before_login.pop(x) #limpa o cache_app_before_login
                    break
        if token_validate:   
            form = ChangePasswordForm()
            if form.validate_on_submit():
                change_password_success = False   
                verification_code = int(token_verification_code[50:56])             
                for x in range(len(cache_app_before_login)):      
                    if verification_code == cache_app_before_login[x][1]: #verifica se o token passado no link é o mesmo que foi gerado pelo sistema                    
                        new_password = form.new_password.data
                        user_recovery_password = User(cache_app_before_login[x][0]['name'], cache_app_before_login[x][0]['email'], new_password) #gera um novo objeto de usuario para atualizar no banco
                        new_password = form.new_password.data
                        database.update('users', cache_app_before_login[x][0], user_recovery_password.get_as_json())
                        cache_app_before_login.pop(x) #limpa o cache_app_before_login
                        change_password_success = True
                        break
                if change_password_success:
                    return redirect(url_for("login"))
                else:
                    return render_template('change_password.html', form=form)
            else:
                return render_template('change_password.html', form=form)
        else:
            abort(404)
    else:
        return redirect(url_for("index"))


#### Tratamento de exceções das rotas ####

@app.errorhandler(404)
def errorPage(e):
    return render_template('404.html', e=e)
    
@app.errorhandler(401)
def page_not_found(e):
    return redirect(url_for("login"))

@app.errorhandler(500)
def errorPage(e):
    return render_template('500.html', e=e)


#### Rotas de teste ####

@app.route("/test/", methods=['GET', 'POST'])
def test():
    return render_template("advanced.html")
global aux
aux=1
@app.route("/test2/", methods=['GET', 'POST'])
def test2():
    res = request.form.getlist("form")
    print(res)
    return redirect(url_for("index"))
