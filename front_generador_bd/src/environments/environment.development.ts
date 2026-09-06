const wsPort = 8000;
const portJava = 7000;
export const environment = {
    production: false,
    wsPort,                // 👈 puerto configurable
    wsPath: '/ws/canvas/',        // 👈 path base
    endpoint_python: `http://127.0.0.1:${wsPort}/`,
    WebSocket_python: `127.0.0.1:${wsPort}`,
    //endpoint_java: `http://127.0.0.1:${portJava}/`
    //endpoint_java: `http://ec2-34-228-19-253.compute-1.amazonaws.com:${portJava}/`
    endpoint_java: `https://spring-sw1.fournext.me/`,
};
