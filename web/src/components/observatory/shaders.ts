/**
 * GLSL sources for the Observatory spectral sigil (animation-spec.md §1).
 *
 * Classic ShaderMaterial (not RawShaderMaterial): three prepends
 * `precision`, `attribute vec3 position`, `uniform mat4 modelViewMatrix`,
 * `uniform mat4 projectionMatrix` etc., so the sources below only declare
 * the custom attributes (`aColor`, `aDisplacement`) and varyings.
 *
 * Custom geometry attributes are bound by name
 * (`geometry.setAttribute("aColor", …)` ⇢ `attribute vec3 aColor`).
 */

export const SIGIL_VERTEX_SHADER = /* glsl */ `
attribute vec3 aColor;
attribute vec3 aDisplacement;
uniform float amplitude;
varying vec3 vColor;

void main() {
  vColor = aColor;
  vec3 displaced = position + amplitude * aDisplacement;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
}
`;

export const SIGIL_FRAGMENT_SHADER = /* glsl */ `
uniform vec3 color;
uniform float opacity;
varying vec3 vColor;

void main() {
  gl_FragColor = vec4(vColor * color, opacity);
}
`;
