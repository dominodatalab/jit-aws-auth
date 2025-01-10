import os,json,argparse

argparser = argparse.ArgumentParser()
argparser.add_argument("-c","--cred-file",help="Path to the AWS credentials file",default=os.getenv("CRED_FILE","/etc/.aws/credentials"))
argparser.add_argument("-p","--profile",help="AWS profile to use")
args = argparser.parse_args()

if __name__ == 'main':
    with open(args.cred_file) as f:
        base_creds = json.load(f)[args.profile]
    # Based on https://docs.aws.amazon.com/cli/v1/userguide/cli-configure-sourcing-external.html 
    # this command should print the credentials in the following structure:
    # {
    #   "Version": 1,
    #   "AccessKeyId": "an AWS access key",
    #   "SecretAccessKey": "your AWS secret access key",
    #   "SessionToken": "the AWS session token for temporary credentials", 
    #   "Expiration": "ISO8601 timestamp when the credentials expire"
    # }
    creds = {}
    creds["Version"] = 1
    for k,v in base_creds.items():
        newk = k.capitalize()
        creds[newk] = v
    print(json.dumps(creds))
    