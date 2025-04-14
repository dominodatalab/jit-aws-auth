package main

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/go-resty/resty/v2"
	"github.com/golang-jwt/jwt/v5"
)

func reqWithToken(tokenString string, url string) (*resty.Response, error) {
	rest_client := resty.New()
	return rest_client.R().SetAuthToken(tokenString).Get(url)
}

func getEnvWithFallback(key, fallback string) string {
	if value, ok := os.LookupEnv(key); ok {
		return value
	}
	return fallback
}

func verifyValidUser(tokenString string, dominoURL string) bool {
	resp, err := reqWithToken(tokenString, dominoURL)
	if err != nil {
		fmt.Printf("Error validating user. Status code: %s, Error %s\n", resp, err)
		return false
	}
	if resp.StatusCode() != 200 {
		return false
	}
	return true
}

func getJITUserProjects(tokenString string, jitURL string) string {
	resp, err := reqWithToken(tokenString, jitURL)
	if err != nil {
		fmt.Printf("Error getting user groups. Status code: %s, Error %s\n", resp, err)
		return resp.String()
	}
	return resp.String()
}

func testProjectCredentials(tokenString string, projectID string, jitURL string) string {
	resp, err := reqWithToken(tokenString, jitURL+"/"+projectID)
	if err != nil {
		fmt.Printf("Error getting credentials for project %s. Status code: %s, Error %s\n", projectID, resp, err)
		return resp.String()
	}
	return resp.String()
}

func parseJWT(tokenString string) *jwt.Token {
	parsedJWT, _, err := jwt.NewParser().ParseUnverified(string(tokenString), make(jwt.MapClaims))
	if err != nil {
		fmt.Printf("Error parsing JWT:\n %s\n", err)
	}
	return parsedJWT
}

func main() {

	token_endpoint_base := getEnvWithFallback("DOMINO_API_PROXY", "http://localhost:8899")
	jit_endpoint_base := "http://jit-svc.domino-field"
	domino_host := getEnvWithFallback("DOMINO_USER_HOST", "http://nucleus-frontend.domino-platform:80")
	userjwt_endpoint := token_endpoint_base + "/access-token"
	user_is_valid_endpoint := domino_host + "/v4/auth/principal"
	user_projects_endpoint := jit_endpoint_base + "/user-projects"

	fmt.Printf("Requesting user JWT from %s...\n", userjwt_endpoint)
	rest_client := resty.New()
	jwt, jwterr := rest_client.R().Get(userjwt_endpoint)
	if jwterr != nil {
		fmt.Printf("Error getting user JWT: %s\n", jwterr)
	}
	user := jwt.String()

	fmt.Printf("Validating user JWT...\n")

	if verifyValidUser(user, user_is_valid_endpoint) {
		fmt.Printf("Valid Domino User JWT!\n")
	} else {
		fmt.Printf("User JWT rejected by Nucleus!\n")
	}
	parsedJWT := parseJWT(user)
	pretty_print, _ := json.MarshalIndent(parsedJWT, "", "    ")

	fmt.Printf("User JWT contents: \n%v\n", string(pretty_print))
	fmt.Printf("Gathering User project list from JIT Proxy...\n")
	user_projects := getJITUserProjects(user, user_projects_endpoint)
	fmt.Printf("User projects: %s\n", string(user_projects))
	var project_array []string
	json.Unmarshal([]byte(user_projects), &project_array)
	fmt.Printf("Testing project credentials for project list: %s\n", project_array)
	for _, project := range project_array {
		project_credential_endpoint := jit_endpoint_base + "/jit_sessions/" + project
		project_credentials := testProjectCredentials(user, project, project_credential_endpoint)
		pretty_print, err := json.MarshalIndent(project_credentials, "", "    ")
		if err != nil {
			fmt.Printf("Error getting credentials for project %s: %s\n", project, project_credentials)
		} else {
			fmt.Printf("Project %s credentials: \n%v\n", project, string(pretty_print))
		}
	}
}
