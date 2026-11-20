Shader "Sitekick/ChipIcon"
{
	// Draws a chip icon's mesh from the colours baked into its vertices.
	//
	// The vector package's gradient shader reads a small gradient atlas in the
	// fragment stage, and that path does not survive the UI mesh: the atlas mapped
	// correctly (texel size and gradient index both verified on the drawn mesh)
	// yet the sampled ramp came out wrong. ChipIconGraphic evaluates the same
	// ramp in C# while it builds the mesh, so this shader only has to paint
	// vertex colours and honour the scroll view's clipping.
	Properties
	{
		_Color ("Tint", Color) = (1,1,1,1)

		_StencilComp ("Stencil Comparison", Float) = 8
		_Stencil ("Stencil ID", Float) = 0
		_StencilOp ("Stencil Operation", Float) = 0
		_StencilWriteMask ("Stencil Write Mask", Float) = 255
		_StencilReadMask ("Stencil Read Mask", Float) = 255
		_ColorMask ("Color Mask", Float) = 15
	}
	SubShader
	{
		Tags
		{
			"RenderType" = "Transparent"
			"Queue" = "Transparent"
			"IgnoreProjector" = "True"
			"PreviewType" = "Plane"
		}

		Stencil
		{
			Ref [_Stencil]
			Comp [_StencilComp]
			Pass [_StencilOp]
			ReadMask [_StencilReadMask]
			WriteMask [_StencilWriteMask]
		}

		Cull Off
		Lighting Off
		ZWrite Off
		ZTest [unity_GUIZTestMode]
		Blend One OneMinusSrcAlpha
		ColorMask [_ColorMask]

		Pass
		{
			CGPROGRAM
			#pragma vertex vert
			#pragma fragment frag
			#pragma multi_compile_local _ UNITY_UI_CLIP_RECT
			#pragma multi_compile_local _ UNITY_UI_ALPHACLIP

			#include "UnityCG.cginc"
			#include "UnityUI.cginc"

			struct appdata
			{
				float4 vertex : POSITION;
				fixed4 color : COLOR;
			};

			struct v2f
			{
				fixed4 color : COLOR;
				float4 worldPosition : TEXCOORD0;
				float4 vertex : SV_POSITION;
			};

			fixed4 _Color;
			float4 _ClipRect;

			v2f vert (appdata IN)
			{
				v2f OUT;
				OUT.vertex = UnityObjectToClipPos(IN.vertex);
				OUT.color = IN.color * _Color;
				OUT.worldPosition = IN.vertex;
				return OUT;
			}

			fixed4 frag (v2f i) : SV_Target
			{
				fixed4 finalColor = i.color;
				finalColor.rgb *= finalColor.a;

				#ifdef UNITY_UI_CLIP_RECT
				finalColor.a *= UnityGet2DClipping(i.worldPosition.xy, _ClipRect);
				#endif

				#ifdef UNITY_UI_ALPHACLIP
				clip(finalColor.a - 0.001);
				#endif

				return finalColor;
			}
			ENDCG
		}
	}
}
