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
	json.Unmarshal(credbytes, &creds)
	pretty_print, _ := json.MarshalIndent(creds[profileName], "", "    ")
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println(string(pretty_print))
}
