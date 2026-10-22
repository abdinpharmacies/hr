const mountSwagger = () => {
    if (!document.getElementById("ab-ecommerce-api-swagger")) {
        return;
    }
    window.SwaggerUIBundle({
        url: "/api/v1/openapi.json",
        dom_id: "#ab-ecommerce-api-swagger",
        deepLinking: true,
        persistAuthorization: false,
        validatorUrl: null,
        filter: true,
        displayRequestDuration: true,
        requestInterceptor: (request) => {
            const target = new URL(request.url, window.location.origin);
            if (target.origin !== window.location.origin) {
                throw new Error();
            }
            request.credentials = target.pathname === "/api/v1/openapi.json" ? "same-origin" : "omit";
            return request;
        },
    });
};

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountSwagger, { once: true });
} else {
    mountSwagger();
}
