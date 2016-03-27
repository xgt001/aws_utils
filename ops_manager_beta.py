#!/usr/bin/python
import boto
import sys
import traceback
from boto.iam import IAMConnection
import boto.opsworks.layer1
import requests
from ConfigParser import SafeConfigParser
import simplejson
import datetime

our_stacks = 0
#We maintain dictionary of Stack vs Stack ID
stack_dict = {}
app_id_list = []
ssl_dict = []


def read_properties():
  try:
    file_check = open('devops_creds.properties','r')
    parser = SafeConfigParser()
    parser.read('devops_creds.properties')
    secret_key = parser.get('Credentials','secret_key')
    access_key = parser.get('Credentials','access_key')
    if (len(access_key)!=20 or len(secret_key)!=40) :
        print "ERROR: Make sure you have entered valid AWS credentials in the properties file"
        print "ERROR: Credentials invalid!"
        print "ERROR: Exiting"
        sys.exit(0)
    return access_key.strip(),secret_key.strip()
  except:
    print "Please make sure if the devops_creds.properties file exists"
    sys.exit(-1)


#get a dictionary of Stack Name vs Stack Id's
def prepare_stack_dict():
    access_key_value,secret_key_value=read_properties()
    #Connect to OpsWorks API
    opsworks = boto.connect_opsworks(access_key_value,secret_key_value)
    our_stacks = opsworks.describe_stacks()
    stack_len = len(our_stacks['Stacks'])
    global stack_dict
    for i in range(0,stack_len):
        stack_name = our_stacks['Stacks'][i]['Name']
        stack_id = our_stacks['Stacks'][i]['StackId']
        stack_dict[stack_name]=stack_id
    print "Initiating"
    return 0


def prepare_app_list():
    access_key_value,secret_key_value=read_properties()
    opsworks = boto.connect_opsworks(access_key_value,secret_key_value)
    prepare_stack_dict()
    global app_id_list
    for stack_id in stack_dict.itervalues():
        get_dict = opsworks.describe_apps(stack_id)
        length = len(get_dict['Apps'])
        for i in range(0,length):
            get_app_id = get_dict['Apps'][i]['AppId']
            app_id_list.append(get_app_id)


def update_all_ssl():
    prepare_app_list()
    access_key_value,secret_key_value=read_properties()
    opsworks = boto.connect_opsworks(access_key_value,secret_key_value)
    for app_id in app_id_list:
        opsworks.update_apps(app_id,SslConfiguration=ssl_dict)
        print "Updated app ssl"+app_id


#Execute recipes
def execute_recipes(stack_name,recipes):
    access_key_value,secret_key_value=read_properties()
    opsworks = boto.connect_opsworks(access_key_value,secret_key_value)
    stack_list = []
    stack_id_list = []
    if ',' in stack_name:
        stack_list = stack_name.split(',')
    elif stack_name == 'all':
        for stack_name,stack_id in stack_dict.iteritems():
            print "Stack ID"+stack_name
            execute_recipes = {}
            execute_recipes['Name']='execute_recipes'
            execute_recipes['Args']={}
            recipes_list = []
            recipes_list.append(recipes)
            execute_recipes['Args']['recipes']=recipes_list
            opsworks.create_deployment(stack_id,execute_recipes)
        return 0
    else:
        stack_list.append(stack_name)
    #Connect to OpsWorks API
    recipes_list = []
    recipes_list.append(recipes)
    execute_recipes = {}
    execute_recipes['Name']='execute_recipes'
    execute_recipes['Args']={}
    execute_recipes['Args']['recipes']=recipes_list
    stacks_to_update = dict((k,stack_dict[k]) for k in stack_list if k in stack_dict)
    print stacks_to_update
    for stack_name,stack_id in stacks_to_update.items():
        print "Executing Recipe in Stack :" + stack_name
        deployment_id = opsworks.create_deployment(stack_id,execute_recipes)
        write_deployment_id = open('temp_deplist','w')
        write_deployment_id.write('EXC'+str(deployment_id.values().pop())+'\n')
        write_deployment_id.close()


#Update Custom Cookbooks globally
def update_custom_cookbooks(stack_name=None):
    access_key_value,secret_key_value=read_properties()
    opsworks = boto.connect_opsworks(access_key_value,secret_key_value)
    stack_list = []
    stack_id_list = []
    if ',' in stack_name:
        stack_list = stack_name.split(',')
    elif stack_name == 'all':
        for stack_name,stack_id in stack_dict.items():
            print "Running Update on"+stack_name
            update_cookbooks = {}
            update_cookbooks['Name']='update_custom_cookbooks'
            opsworks.create_deployment(stack_id,update_cookbooks)
        return 0
    else:
        stack_list.append(stack_name)
    #Connect to OpsWorks API
    update_cookbooks = {}
    update_cookbooks['Name']='update_custom_cookbooks'
    stacks_to_update = dict((k,stack_dict[k]) for k in stack_list if k in stack_dict)
    print stacks_to_update
    for stack_name,stack_id in stacks_to_update.items():
        deployment_id = opsworks.create_deployment(stack_id,update_cookbooks)
        print "Triggered Update on: "+stack_name
        write_deployment_id = open('temp_deplist','w')
        write_deployment_id.write('UPG'+str(deployment_id.values().pop())+'\n')
        write_deployment_id.close()


def update_all_layers(recipe,update_type=None):
    access_key_value,secret_key_value=read_properties()

    #Connect to OpsWorks API
    opsworks = boto.connect_opsworks(access_key_value,secret_key_value)
    our_stacks = opsworks.describe_stacks()
    stack_len = len(our_stacks['Stacks'])
    print "WARNING: I AM UPDATING LAYERS IN EACH AND EVERY STACK"
    print "WARNING: BEWARE OF WHAT YOU ARE GOING TO DO"
    if raw_input("Type 'yes' to Confirm :")=='yes':
        for stack_name,stack_id in stack_dict.items():
            get_layer_details = opsworks.describe_layers(stack_id=stack_id)
            layer_length=len(get_layer_details['Layers'])
            print "Found "+str(layer_length)+" layers in the stack "+stack_name
            for i in range(0,layer_length):
                layer_id = get_layer_details['Layers'][i]['LayerId']
                custom_recipes = get_layer_details['Layers'][i]['CustomRecipes']

                #Extract Deploy and Setup Recipes seperately and save them to respective lists
                deploy_recipe_list=get_layer_details['Layers'][i]['CustomRecipes']['Deploy']
                setup_recipe_list=get_layer_details['Layers'][i]['CustomRecipes']['Setup']
                undeploy_recipe_list=get_layer_details['Layers'][i]['CustomRecipes']['Undeploy']
                shutdown_recipe_list=get_layer_details['Layers'][i]['CustomRecipes']['Shutdown']
                configure_recipe_list=get_layer_details['Layers'][i]['CustomRecipes']['Configure']

                #update our dictionary for Deploy and Setup lists
                if update_type == None:
                    '''
                    Dictionary is mapped to the copy after being assigned, so we don't need to update the copy explicitly.
                    '''
                    deploy_recipe_list.append(recipe)
                    setup_recipe_list.append(recipe)
                    undeploy_recipe_list.append(recipe)
                    shutdown_recipe_list.append(recipe)
                    configure_recipe_list.append(recipe)

                    get_layer_details['Layers'][i]['CustomRecipes']['Deploy']=deploy_recipe_list
                    get_layer_details['Layers'][i]['CustomRecipes']['Setup']=setup_recipe_list
                    get_layer_details['Layers'][i]['CustomRecipes']['Configure']=configure_recipe_list
                    get_layer_details['Layers'][i]['CustomRecipes']['Undeploy']=undeploy_recipe_list
                    get_layer_details['Layers'][i]['CustomRecipes']['Shutdown']=shutdown_recipe_list
                    print "Updating All"
                elif update_type == 'Setup':
                    setup_recipe_list.append(recipe)
                    get_layer_details['Layers'][i]['CustomRecipes']['Setup']=setup_recipe_list
                    opsworks.update_layer(layer_id=layer_id,custom_recipes=custom_recipes)
                elif update_type == 'Deploy':
                    deploy_recipe_list.append(recipe)
                    get_layer_details['Layers'][i]['CustomRecipes']['Deploy']=deploy_recipe_list
                elif update_type == 'Configure':
                    configure_recipe_list.append(recipe)
                    get_layer_details['Layers'][i]['CustomRecipes']['Configure']=configure_recipe_list
                elif update_type == 'Undeploy':
                    undeploy_recipe_list.append(recipe)
                    get_layer_details['Layers'][i]['CustomRecipes']['Undeploy']=undeploy_recipe_list
                elif update_type == 'Shutdown':
                    shutdown_recipe_list.append(recipe)
                    get_layer_details['Layers'][i]['CustomRecipes']['Shutdown']=shutdown_recipe_list
                else:
                    print "Invalid Recipe List found, terminating \n"
                    sys.exit(0)
                try:
                    opsworks.update_layer(layer_id=layer_id,custom_recipes=custom_recipes)
                    print "Updated: "+stack_name
                except Exception,err:
                    print "Caught an exception:"
                    traceback.print_exc(file=sys.stdout)
        else:
            print "Aborting"
            sys.exit(0)


def update_layer(stack_name,recipe,update_type=None):
    print "DEBUG: Inside Update method"
    access_key_value,secret_key_value=read_properties()
    #Connect to OpsWorks API
    opsworks = boto.connect_opsworks(access_key_value,secret_key_value)
    get_layer_details = opsworks.describe_layers(stack_id=stack_dict[stack_name])
    layer_length = len(get_layer_details['Layers'])
    print "Found "+str(layer_length)+" layers"
    for i in range(0,layer_length):
        layer_id = get_layer_details['Layers'][i]['LayerId']
        custom_recipes = get_layer_details['Layers'][i]['CustomRecipes']

        #Extract Deploy and Setup Recipes seperately and save them to respective lists
        deploy_recipe_list=get_layer_details['Layers'][i]['CustomRecipes']['Deploy']
        setup_recipe_list=get_layer_details['Layers'][i]['CustomRecipes']['Setup']
        undeploy_recipe_list=get_layer_details['Layers'][i]['CustomRecipes']['Undeploy']
        shutdown_recipe_list=get_layer_details['Layers'][i]['CustomRecipes']['Shutdown']
        configure_recipe_list=get_layer_details['Layers'][i]['CustomRecipes']['Configure']

        #update our dictionary for Deploy and Setup lists


        if update_type == None:
            '''
            Dictionary is mapped to the copy after being assigned, so we don't need to update the copy explicitly.
            '''
            deploy_recipe_list.append(recipe)
            setup_recipe_list.append(recipe)
            undeploy_recipe_list.append(recipe)
            shutdown_recipe_list.append(recipe)
            configure_recipe_list.append(recipe)

            get_layer_details['Layers'][i]['CustomRecipes']['Deploy']=deploy_recipe_list
            get_layer_details['Layers'][i]['CustomRecipes']['Setup']=setup_recipe_list
            get_layer_details['Layers'][i]['CustomRecipes']['Configure']=configure_recipe_list
            get_layer_details['Layers'][i]['CustomRecipes']['Undeploy']=undeploy_recipe_list
            get_layer_details['Layers'][i]['CustomRecipes']['Shutdown']=shutdown_recipe_list
            print "Updating All"
        elif update_type == 'Setup':
            setup_recipe_list.append(recipe)
            get_layer_details['Layers'][i]['CustomRecipes']['Setup']=setup_recipe_list
        elif update_type == 'Deploy':
            deploy_recipe_list.append(recipe)
            get_layer_details['Layers'][i]['CustomRecipes']['Deploy']=deploy_recipe_list
        elif update_type == 'Configure':
            configure_recipe_list.append(recipe)
            get_layer_details['Layers'][i]['CustomRecipes']['Configure']=configure_recipe_list
        elif update_type == 'Undeploy':
            undeploy_recipe_list.append(recipe)
            get_layer_details['Layers'][i]['CustomRecipes']['Undeploy']=undeploy_recipe_list
        elif update_type == 'Shutdown':
            shutdown_recipe_list.append(recipe)
            get_layer_details['Layers'][i]['CustomRecipes']['Shutdown']=shutdown_recipe_list
        else:
            print "Invalid Recipe List found, terminating \n"
            sys.exit(0)
        try:
            opsworks.update_layer(layer_id=layer_id,custom_recipes=custom_recipes)
            print "Updated!"
        except Exception,err:
            print "Caught an exception:"
            traceback.print_exc(file=sys.stdout)
    return 0


def show_help():
    print 'OpsManager v:0.1'
    print '''CommandLine tool for AWS OpsWorks'''
    print '''To search for a given string across all stack setting jsons. Usage: ./ops_manager.py --find <string> '''
    print '''Example ./ops_manager --find qb0x.com'''
    print '''To replace a value in each and every stack, do: ./ops_manager.py --update-stacks \n'''
    print '''To insert a custom recipe to a given stack,
    do: ./ops_manager.py --update-layer <layer_to_update> --recipe <recipe_to_add> [--type Shutdown|Deploy|Configure|Undeploy|Setup]
    If none specified, then all the 5 configs are updated.
    Sample usage :./ops_manager.py --update-layer DevOps --recipe mysql_fresh --type Shutdown
    The above adds the recipe mysql_fresh only to Shutdown config.
    ./ops_manager.py --update-layer DevOps --recipe mysql_fresh
    Updates all 5 configurations for devops. \n

    To update custom cookbooks:
    ./ops_manager.py --update-custom-cookbooks [StackName,comma seperated]
    Ex:
    ./ops_manager.py --update-custom-cookbooks Devops,Dev2

    To Update Custom Cookbooks across all stacks:
    ./ops_manager.py --update-custom-cookbooks all

    To Execute recipes:

    ./ops_manager.py --update-custom-cookbooks [StackName,comma seperated] [Recipe Name, comma seperated]

    ./ops_manager.py --update-custom-cookbooks Dev2 monit-ng::unicorn

    To Execute Recipes Across every stack:

    ./ops_manager.py --update-custom-cookbooks all [your-recipes]

    To Check Status of Your Upgrade or Execute Recipes

    ./ops_manager.py --check-deployment-status

    To Create Snapshots for all volumes:
    ./ops_manager_beta.py --create-snapshots ap-southeast-1(us-east-1)

    '''
    print '''Thermonuclear!!! To update all the layers across all stacks (NOT RECOMMENDED)
    ./ops_manager.py --update-all-layers'''


def add_parameter(stack=None):
    access_key_value,secret_key_value=read_properties()
    opsworks = boto.connect_opsworks(access_key_value,secret_key_value)
    print "Connected to AWS OpsWorks \n"
    our_stacks = opsworks.describe_stacks()
    key = str(raw_input("Enter key to add JSON:")).strip()
    value = str(raw_input("Enter value:")).strip()
    print "Key is "+key
    print "value is"+value
    if type(stack)!=None and len(stack)> 0:
        for i in range(0,len(our_stacks['Stacks'])):
            if (our_stacks['Stacks'][i]['Name'] == stack.strip()):
                print 'Updating Stack:' + str(our_stacks['Stacks'][i]['Name'])
                updated_stack = our_stacks['Stacks'][i]['CustomJson']
                json_dict=simplejson.loads(our_stacks['Stacks'][i]['CustomJson'])
                json_dict[key]=value
                fixed_json_dict = simplejson.dumps(json_dict,sort_keys=False,indent=3*' ')
                opsworks.update_stack(our_stacks['Stacks'][i]['StackId'],custom_json=fixed_json_dict)
    else:
        for i in range(0,len(our_stacks['Stacks'])):
            if 'CustomJson' in our_stacks['Stacks'][i]:
                print "Total stacks to be updated:"+str(len(our_stacks['Stacks']))
                print "Updating Stack: "+our_stacks['Stacks'][i]['Name']
                updated_stack = our_stacks['Stacks'][i]['CustomJson']
                json_dict=simplejson.loads(our_stacks['Stacks'][i]['CustomJson'])
                json_dict[key]=value
                fixed_json_dict = simplejson.dumps(json_dict,sort_keys=False,indent=3*' ').replace('\\"','"').replace('"{','{').replace('}"','}')
                # print "Text:"+str(fixed_json_dict['nodejs'])
                # print fixed_json_dict
                opsworks.update_stack(our_stacks['Stacks'][i]['StackId'],custom_json=fixed_json_dict)
            else:
                print "Couldn't find custom json field"
    return 0


def update_stacks():
    access_key_value,secret_key_value=read_properties()
    opsworks = boto.connect_opsworks(access_key_value,secret_key_value)
    print "Connected to AWS OpsWorks \n"
    global our_stacks
    our_stacks = opsworks.describe_stacks()
    stack_len = len(our_stacks['Stacks'])
    print "Number of Stacks to be udpated: "+str(stack_len)
    change_param=int(raw_input("Number of Parameters to Change? \n"))
    list_original=[]
    list_update=[]
    for k in range(0,change_param):
        print str(k)+"of"+str(change_param)
        original_value = str(raw_input('Enter the original value to replace: \n')).strip()
        update_value = str(raw_input('Enter the updated value: \n')).strip()
        list_original.append(original_value)
        list_update.append(update_value)
    for i in range(0,stack_len):
        if 'CustomJson' in our_stacks['Stacks'][i]:
            print 'Updating Stack:' + str(our_stacks['Stacks'][i]['Name'])
            my_customjson = our_stacks['Stacks'][i]['CustomJson']
            update_json = my_customjson
            for k in range(0,change_param):
                update_json = update_json.replace(list_original[k],list_update[k])
            our_stacks['Stacks'][i]['CustomJson'] = update_json
            opsworks.update_stack(our_stacks['Stacks'][i]['StackId'],custom_json=update_json)
        else :
            print 'Skipping Stack:' + str(our_stacks['Stacks'][i]['Name']) +' as there is no CustomJSON defined \n'
    print 'Exiting'


def check_deployment_status():
    access_key_value,secret_key_value=read_properties()
    opsworks = boto.connect_opsworks(access_key_value,secret_key_value)
    check_status = open('temp_deplist','r')
    for line in check_status.read().splitlines():
        print line
        dep_id = []
        dep_id.append(line[3:])
        print str(dep_id)
        if line[0:3] == 'UPG':
            response = opsworks.describe_deployments(deployment_ids=dep_id)
            print "Custom Cookbook Update Status is \n" + response['Deployments'][0]['Status']
            print "Stack :" + response['Deployments'][0]['StackId']
        elif line[0:3] == 'EXC':
            print "Recipe Execution Status is \n"
            print opsworks.describe_deployments(deployment_ids=dep_id)


def find_in_stack(search_string):
    access_key_value,secret_key_value=read_properties()
    access_key_value=access_key_value.strip()
    secret_key_value=secret_key_value.strip()
    opsworks = boto.connect_opsworks(access_key_value,secret_key_value)
    print "Connected to AWS OpsWorks"
    result_flag = 0
    our_stacks = opsworks.describe_stacks()
    stack_len = len(our_stacks['Stacks'])
    for i in range(0,stack_len):
        if 'CustomJson' in our_stacks['Stacks'][i]:
            my_customjson = our_stacks['Stacks'][i]['CustomJson']
            update_json = my_customjson
            test = update_json.find(search_string)
            if test!=-1:
                result_flag =1
                print "Found in "+str(our_stacks['Stacks'][i]['Name'])
    if result_flag == 0:
        print "No results found."
    print 'Exiting'


def create_snapshots(region=None):
    access_key_value, secret_key_value = read_properties()
    access_key_value = access_key_value.strip()
    secret_key_value = secret_key_value.strip()
    boto.connect_ec2(access_key_value, secret_key_value)
    if region:
        ec2 = boto.ec2.connect_to_region(region)
    all_volumes = ec2.get_all_volumes()
    all_volume_ids = []
    for volume in all_volumes:
        vol_id = str(volume).split(':')[1]
        all_volume_ids.append(vol_id)
    print len(all_volume_ids)
    try:
        for vol_id in all_volume_ids:
            description = str(datetime.datetime.now())
            description = description.split(' ')[0] + 'auto snapshot for: ' + vol_id
            ec2.create_snapshot(vol_id, description, dry_run=False)
            print 'Created a snapshot for:'+vol_id
    except Exception, e:
        print 'Sergeant, we hit a roadblock!'
        print e


if __name__ == '__main__':
    try:
        if sys.argv[1] == '--update-layer':
            print "DEBUG: Update Requested "
            if len(sys.argv) < 5 or sys.argv[3]!='--recipe':
                show_help()
                sys.exit(0)
            else:
                stack_name,recipe=sys.argv[2],sys.argv[4]
                if len(sys.argv)==7:
                    prepare_stack_dict()
                    update_type=sys.argv[6]
                    update_layer(stack_name,recipe,update_type)
                else:
                    prepare_stack_dict()
                    update_layer(stack_name,recipe)
        elif sys.argv[1] == '--update-all':
            if len(sys.argv) < 6 or sys.argv[2]!='--recipe':
                show_help()
                sys.exit(0)
            else:
                recipe,update_type=sys.argv[3],sys.argv[5]
                prepare_stack_dict()
                update_all_layers(recipe,update_type)
        elif sys.argv[1] == '--list-stacks':
            prepare_stack_dict()
            # print stack_dict
            for key in stack_dict.iterkeys():
                print key
            sys.exit(0)
        elif sys.argv[1] == '--add-value':
            if len(sys.argv) >= 2:
                prepare_stack_dict()
                if len(sys.argv) == 3:
                    add_parameter(sys.argv[2])
                elif len(sys.argv) == 2:
                    add_parameter()
            else:
                print len(sys.argv)
                show_help()
        elif sys.argv[1] == '--find':
            prepare_stack_dict()
            find_in_stack(sys.argv[2])
        elif sys.argv[1] == '--update-stacks':
            update_stacks()
        elif sys.argv[1] == '--get-apps':
            prepare_app_list()
        elif sys.argv[1] == '--update-ssl':
            update_all_ssl()
        elif sys.argv[1] == '--update-custom-cookbooks':
            prepare_stack_dict()
            update_custom_cookbooks(sys.argv[2])
        elif sys.argv[1] == '--execute-recipes':
            prepare_stack_dict()
            execute_recipes(sys.argv[2],sys.argv[3])
        elif sys.argv[1] == '--check-deployment-status':
            check_deployment_status()
        elif sys.argv[1] == '--create-snapshots':
            region = sys.argv[2]
            create_snapshots(region)
        else:
            show_help()
    except IndexError:
        show_help()
        # traceback.print_exc(file=sys.stdout)
    except Exception,err:
        traceback.print_exc(file=sys.stdout)
