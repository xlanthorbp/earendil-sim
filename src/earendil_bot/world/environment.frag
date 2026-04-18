varying vec3 vNormal;
varying vec3 vPosition;

void main()
{
    vec3 normal = normalize(vNormal);
    // Flip normal for back faces so lighting works from both sides
    if (!gl_FrontFacing) normal = -normal;

    vec3 lightDir = normalize(vec3(0.5, -0.1, 0.9));
    vec3 viewDir = normalize(-vPosition);

    // Ambient + diffuse + specular
    float ambient = 0.3;
    float diff = max(dot(normal, lightDir), 0.0);
    vec3 halfDir = normalize(lightDir + viewDir);
    float spec = pow(max(dot(normal, halfDir), 0.0), 20.0);

    vec3 baseColor = vec3(0.87, 0.72, 0.53);
    vec3 result = baseColor * (ambient + 0.7 * diff) + vec3(0.15) * spec;

    gl_FragColor = vec4(result, 1.0);
}
