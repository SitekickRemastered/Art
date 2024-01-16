// Made with Amplify Shader Editor
// Available at the Unity Asset Store - http://u3d.as/y3X 
Shader "Sitekick/Paint"
{
	Properties
	{
		[PerRendererData]_MainTex("MainTex", 2D) = "white" {}
		[PerRendererData]_MaskTex("MaskTex", 2D) = "white" {}
		_Color("Color", Color) = (1,1,1,1)
		_Multiplier("Multiplier", Vector) = (0,0,0,0)
		_Offset("Offset", Vector) = (0,0,0,0)
		[HideInInspector] _texcoord( "", 2D ) = "white" {}
		[HideInInspector] __dirty( "", Int ) = 1
	}

	SubShader
	{
		Tags{ "RenderType" = "Transparent"  "Queue" = "Transparent+0" "IgnoreProjector" = "True" "IsEmissive" = "true"  }
		Cull Back
		CGPROGRAM
		#pragma target 3.0
		#pragma surface surf Unlit alpha:fade keepalpha noshadow 
		struct Input
		{
			float2 uv_texcoord;
			float4 vertexColor : COLOR;
		};

		uniform sampler2D _MainTex;
		uniform float4 _MainTex_ST;
		uniform sampler2D _MaskTex;
		uniform float4 _MaskTex_ST;
		uniform float4 _Color;
		uniform float3 _Multiplier;
		uniform float3 _Offset;

		inline half4 LightingUnlit( SurfaceOutput s, half3 lightDir, half atten )
		{
			return half4 ( 0, 0, 0, s.Alpha );
		}

		void surf( Input i , inout SurfaceOutput o )
		{
			float2 uv_MainTex = i.uv_texcoord * _MainTex_ST.xy + _MainTex_ST.zw;
			float4 tex2DNode50 = tex2D( _MainTex, uv_MainTex );
			float3 Base53 = (tex2DNode50).rgb;
			float2 uv_MaskTex = i.uv_texcoord * _MaskTex_ST.xy + _MaskTex_ST.zw;
			float Mask52 = tex2D( _MaskTex, uv_MaskTex ).r;
			float3 temp_cast_0 = (Mask52).xxx;
			float3 Diffuse57 = ( Base53 - temp_cast_0 );
			float3 Multiplier20 = _Multiplier;
			float3 Offset25 = _Offset;
			float3 temp_output_5_0 = ( Diffuse57 + (( ( ( _Color * i.vertexColor * Mask52 ) * float4( Multiplier20 , 0.0 ) ) + float4( ( Mask52 * Offset25 ) , 0.0 ) )).rgb );
			float3 Emission86 = temp_output_5_0;
			o.Emission = Emission86;
			float Alpha54 = ( tex2DNode50.a * i.vertexColor.a );
			o.Alpha = Alpha54;
		}

		ENDCG
	}
	CustomEditor "ASEMaterialInspector"
}
/*ASEBEGIN
Version=17500
0;0;1920;1011;1394.428;-313.8925;1;True;True
Node;AmplifyShaderEditor.CommentaryNode;85;-1664,-896;Inherit;False;748.3607;1013;;12;54;57;49;48;47;52;53;51;84;50;92;93;Textures;1,0.5424528,0.5424528,1;0;0
Node;AmplifyShaderEditor.SamplerNode;50;-1632,-768;Inherit;True;Property;_MainTex;MainTex;0;1;[PerRendererData];Create;True;0;0;False;0;-1;None;None;True;0;False;white;Auto;False;Object;-1;Auto;Texture2D;6;0;SAMPLER2D;;False;1;FLOAT2;0,0;False;2;FLOAT;0;False;3;FLOAT2;0,0;False;4;FLOAT2;0,0;False;5;FLOAT;1;False;5;COLOR;0;FLOAT;1;FLOAT;2;FLOAT;3;FLOAT;4
Node;AmplifyShaderEditor.CommentaryNode;11;-864,-896;Inherit;False;927;323;;6;20;19;14;13;12;91;Multiplier;1,1,1,1;0;0
Node;AmplifyShaderEditor.CommentaryNode;15;-864,-480;Inherit;False;928;324;;6;18;23;16;17;25;90;Offset;1,1,1,1;0;0
Node;AmplifyShaderEditor.SamplerNode;51;-1632,-384;Inherit;True;Property;_MaskTex;MaskTex;1;1;[PerRendererData];Create;True;0;0;False;0;-1;None;None;True;0;False;white;Auto;False;Object;-1;Auto;Texture2D;6;0;SAMPLER2D;;False;1;FLOAT2;0,0;False;2;FLOAT;0;False;3;FLOAT2;0,0;False;4;FLOAT2;0,0;False;5;FLOAT;1;False;5;COLOR;0;FLOAT;1;FLOAT;2;FLOAT;3;FLOAT;4
Node;AmplifyShaderEditor.Vector3Node;91;-320,-800;Inherit;False;Property;_Multiplier;Multiplier;3;0;Create;True;0;0;False;0;0,0,0;1,1,1;0;4;FLOAT3;0;FLOAT;1;FLOAT;2;FLOAT;3
Node;AmplifyShaderEditor.Vector3Node;90;-320,-384;Inherit;False;Property;_Offset;Offset;7;0;Create;True;0;0;False;0;0,0,0;0,0,0;0;4;FLOAT3;0;FLOAT;1;FLOAT;2;FLOAT;3
Node;AmplifyShaderEditor.ComponentMaskNode;84;-1312,-832;Inherit;False;True;True;True;False;1;0;COLOR;0,0,0,0;False;1;FLOAT3;0
Node;AmplifyShaderEditor.RegisterLocalVarNode;52;-1120,-384;Inherit;True;Mask;-1;True;1;0;FLOAT;0;False;1;FLOAT;0
Node;AmplifyShaderEditor.CommentaryNode;88;-1664,256;Inherit;False;1874;870;;16;6;22;42;7;28;26;29;32;41;27;30;62;5;64;63;86;Blend;0.3726415,0.7182781,1,1;0;0
Node;AmplifyShaderEditor.RegisterLocalVarNode;20;-144,-768;Inherit;False;Multiplier;-1;True;1;0;FLOAT3;0,0,0;False;1;FLOAT3;0
Node;AmplifyShaderEditor.GetLocalVarNode;42;-1616,768;Inherit;False;52;Mask;1;0;OBJECT;;False;1;FLOAT;0
Node;AmplifyShaderEditor.RegisterLocalVarNode;53;-1120,-832;Inherit;True;Base;-1;True;1;0;FLOAT3;0,0,0;False;1;FLOAT3;0
Node;AmplifyShaderEditor.RegisterLocalVarNode;25;-144,-352;Inherit;False;Offset;-1;True;1;0;FLOAT3;0,0,0;False;1;FLOAT3;0
Node;AmplifyShaderEditor.ColorNode;6;-1616,304;Inherit;False;Property;_Color;Color;2;0;Create;True;0;0;False;0;1,1,1,1;1,1,1,1;True;0;5;COLOR;0;FLOAT;1;FLOAT;2;FLOAT;3;FLOAT;4
Node;AmplifyShaderEditor.VertexColorNode;22;-1616,560;Inherit;False;0;5;COLOR;0;FLOAT;1;FLOAT;2;FLOAT;3;FLOAT;4
Node;AmplifyShaderEditor.SimpleMultiplyOpNode;7;-1328,496;Inherit;False;3;3;0;COLOR;0,0,0,0;False;1;COLOR;0,0,0,0;False;2;FLOAT;0;False;1;COLOR;0
Node;AmplifyShaderEditor.GetLocalVarNode;48;-1632,0;Inherit;False;52;Mask;1;0;OBJECT;;False;1;FLOAT;0
Node;AmplifyShaderEditor.GetLocalVarNode;26;-1328,752;Inherit;False;20;Multiplier;1;0;OBJECT;;False;1;FLOAT3;0
Node;AmplifyShaderEditor.GetLocalVarNode;27;-1328,1008;Inherit;False;25;Offset;1;0;OBJECT;;False;1;FLOAT3;0
Node;AmplifyShaderEditor.GetLocalVarNode;47;-1632,-128;Inherit;False;53;Base;1;0;OBJECT;;False;1;FLOAT3;0
Node;AmplifyShaderEditor.GetLocalVarNode;41;-1328,880;Inherit;False;52;Mask;1;0;OBJECT;;False;1;FLOAT;0
Node;AmplifyShaderEditor.SimpleSubtractOpNode;49;-1376,-128;Inherit;False;2;0;FLOAT3;0,0,0;False;1;FLOAT;0;False;1;FLOAT3;0
Node;AmplifyShaderEditor.SimpleMultiplyOpNode;32;-1104,944;Inherit;False;2;2;0;FLOAT;0;False;1;FLOAT3;0,0,0;False;1;FLOAT3;0
Node;AmplifyShaderEditor.SimpleMultiplyOpNode;28;-1104,624;Inherit;False;2;2;0;COLOR;0,0,0,0;False;1;FLOAT3;0,0,0;False;1;COLOR;0
Node;AmplifyShaderEditor.RegisterLocalVarNode;57;-1120,-128;Inherit;True;Diffuse;-1;True;1;0;FLOAT3;0,0,0;False;1;FLOAT3;0
Node;AmplifyShaderEditor.SimpleAddOpNode;29;-848,752;Inherit;False;2;2;0;COLOR;0,0,0,0;False;1;FLOAT3;0,0,0;False;1;COLOR;0
Node;AmplifyShaderEditor.VertexColorNode;92;-1504,-560;Inherit;False;0;5;COLOR;0;FLOAT;1;FLOAT;2;FLOAT;3;FLOAT;4
Node;AmplifyShaderEditor.ComponentMaskNode;30;-688,752;Inherit;False;True;True;True;False;1;0;COLOR;0,0,0,0;False;1;FLOAT3;0
Node;AmplifyShaderEditor.GetLocalVarNode;62;-688,560;Inherit;False;57;Diffuse;1;0;OBJECT;;False;1;FLOAT3;0
Node;AmplifyShaderEditor.SimpleMultiplyOpNode;93;-1280,-576;Inherit;False;2;2;0;FLOAT;0;False;1;FLOAT;0;False;1;FLOAT;0
Node;AmplifyShaderEditor.SimpleAddOpNode;5;-400,656;Inherit;False;2;2;0;FLOAT3;0,0,0;False;1;FLOAT3;0,0,0;False;1;FLOAT3;0
Node;AmplifyShaderEditor.CommentaryNode;89;256,-896;Inherit;False;529;497;;3;0;87;43;Output;1,1,1,1;0;0
Node;AmplifyShaderEditor.RegisterLocalVarNode;86;-16,752;Inherit;False;Emission;-1;True;1;0;FLOAT3;0,0,0;False;1;FLOAT3;0
Node;AmplifyShaderEditor.RegisterLocalVarNode;54;-1120,-608;Inherit;True;Alpha;-1;True;1;0;FLOAT;0;False;1;FLOAT;0
Node;AmplifyShaderEditor.SimpleMultiplyOpNode;64;-176,752;Inherit;False;2;2;0;FLOAT3;0,0,0;False;1;FLOAT;0;False;1;FLOAT3;0
Node;AmplifyShaderEditor.RangedFloatNode;18;-816,-336;Inherit;False;Property;_OffsetG;OffsetG;9;0;Create;True;0;0;False;0;0;0;-1;1;0;1;FLOAT;0
Node;AmplifyShaderEditor.RangedFloatNode;13;-816,-752;Inherit;False;Property;_MultiplierG;MultiplierG;5;0;Create;True;0;0;False;0;1;1;-1;1;0;1;FLOAT;0
Node;AmplifyShaderEditor.RangedFloatNode;16;-816,-416;Inherit;False;Property;_OffsetR;OffsetR;8;0;Create;True;0;0;False;0;0;0;-1;1;0;1;FLOAT;0
Node;AmplifyShaderEditor.DynamicAppendNode;23;-480,-352;Inherit;False;FLOAT3;4;0;FLOAT;0;False;1;FLOAT;0;False;2;FLOAT;0;False;3;FLOAT;0;False;1;FLOAT3;0
Node;AmplifyShaderEditor.RangedFloatNode;14;-816,-672;Inherit;False;Property;_MultiplierB;MultiplierB;6;0;Create;True;0;0;False;0;1;1;-1;1;0;1;FLOAT;0
Node;AmplifyShaderEditor.GetLocalVarNode;43;304,-656;Inherit;False;54;Alpha;1;0;OBJECT;;False;1;FLOAT;0
Node;AmplifyShaderEditor.DynamicAppendNode;19;-480,-768;Inherit;False;FLOAT3;4;0;FLOAT;0;False;1;FLOAT;0;False;2;FLOAT;0;False;3;FLOAT;0;False;1;FLOAT3;0
Node;AmplifyShaderEditor.GetLocalVarNode;87;304,-816;Inherit;False;86;Emission;1;0;OBJECT;;False;1;FLOAT3;0
Node;AmplifyShaderEditor.RangedFloatNode;17;-816,-256;Inherit;False;Property;_OffsetB;OffsetB;10;0;Create;True;0;0;False;0;0;0;-1;1;0;1;FLOAT;0
Node;AmplifyShaderEditor.RangedFloatNode;12;-816,-832;Inherit;False;Property;_MultiplierR;MultiplierR;4;0;Create;True;0;0;False;0;1;1;-1;1;0;1;FLOAT;0
Node;AmplifyShaderEditor.GetLocalVarNode;63;-400,848;Inherit;False;54;Alpha;1;0;OBJECT;;False;1;FLOAT;0
Node;AmplifyShaderEditor.StandardSurfaceOutputNode;0;528,-848;Float;False;True;-1;2;ASEMaterialInspector;0;0;Unlit;Sitekick/Paint;False;False;False;False;False;False;False;False;False;False;False;False;False;False;True;False;False;False;False;False;False;Back;0;False;-1;0;False;-1;False;0;False;-1;0;False;-1;False;0;Transparent;0.5;True;False;0;False;Transparent;;Transparent;All;14;all;True;True;True;True;0;False;-1;False;0;False;-1;255;False;-1;255;False;-1;0;False;-1;0;False;-1;0;False;-1;0;False;-1;0;False;-1;0;False;-1;0;False;-1;0;False;-1;False;2;15;10;25;False;0.5;False;2;5;False;-1;10;False;-1;0;0;False;-1;0;False;-1;0;False;-1;0;False;-1;0;False;0;0,0,0,0;VertexOffset;True;False;Cylindrical;False;Relative;0;;-1;-1;-1;-1;0;False;0;0;False;-1;-1;0;False;-1;0;0;0;False;0.1;False;-1;0;False;-1;15;0;FLOAT3;0,0,0;False;1;FLOAT3;0,0,0;False;2;FLOAT3;0,0,0;False;3;FLOAT;0;False;4;FLOAT;0;False;6;FLOAT3;0,0,0;False;7;FLOAT3;0,0,0;False;8;FLOAT;0;False;9;FLOAT;0;False;10;FLOAT;0;False;13;FLOAT3;0,0,0;False;11;FLOAT3;0,0,0;False;12;FLOAT3;0,0,0;False;14;FLOAT4;0,0,0,0;False;15;FLOAT3;0,0,0;False;0
WireConnection;84;0;50;0
WireConnection;52;0;51;1
WireConnection;20;0;91;0
WireConnection;53;0;84;0
WireConnection;25;0;90;0
WireConnection;7;0;6;0
WireConnection;7;1;22;0
WireConnection;7;2;42;0
WireConnection;49;0;47;0
WireConnection;49;1;48;0
WireConnection;32;0;41;0
WireConnection;32;1;27;0
WireConnection;28;0;7;0
WireConnection;28;1;26;0
WireConnection;57;0;49;0
WireConnection;29;0;28;0
WireConnection;29;1;32;0
WireConnection;30;0;29;0
WireConnection;93;0;50;4
WireConnection;93;1;92;4
WireConnection;5;0;62;0
WireConnection;5;1;30;0
WireConnection;86;0;5;0
WireConnection;54;0;93;0
WireConnection;64;0;5;0
WireConnection;64;1;63;0
WireConnection;23;0;16;0
WireConnection;23;1;18;0
WireConnection;23;2;17;0
WireConnection;19;0;12;0
WireConnection;19;1;13;0
WireConnection;19;2;14;0
WireConnection;0;2;87;0
WireConnection;0;9;43;0
ASEEND*/
//CHKSM=37DBDFC999DA2C3FD1FC88861A52805B30C57953