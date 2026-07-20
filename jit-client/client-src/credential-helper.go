package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
)

func main() {
	var (
		credFile    string
		profileName string
		// printcred   string
		creds map[string]interface{}
	)

	flag.StringVar(&credFile, "credfile", "/etc/.aws/credentials", "Path to the credential file")
	flag.StringVar(&profileName, "profile", "domino-dummy", "Name of the profile to use")
	flag.Parse()

	credbytes, err := os.ReadFile(credFile)
	if err != nil {
		log.Fatal(err)
	}
	if err := json.Unmarshal(credbytes, &creds); err != nil {
		log.Fatal(err)
	}
	cred, ok := creds[profileName]
	if !ok {
		log.Fatalf("no credentials found for profile %q", profileName)
	}
	pretty_print, err := json.MarshalIndent(cred, "", "    ")
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println(string(pretty_print))
}
