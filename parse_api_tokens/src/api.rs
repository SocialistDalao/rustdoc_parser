use serde_json::Value;
use syn::{GenericArgument, GenericParam, Item, PathArguments, ReturnType, Type};

use std::collections::HashSet;

/// Input Content Example:
///     {"api":"fn try_unwrap(this: Self) -> Result<T, Self>","duration":0,"head":"Methods","impl":"impl<T> Arc<T>","next_api_index":-1,"stability":[],"submodule":"alloc::arc::Arc"}
pub fn is_api_same(api1: &Value, api2: &Value) -> bool {
    api1["impl"] == api2["impl"] && api1["api"] == api2["api"]
}

pub fn is_api_similar(api1: &Value, api2: &Value) -> bool {
    let impl1 = api1["impl"].as_str().unwrap();
    let impl2 = api2["impl"].as_str().unwrap();
    if !compare_api(impl1, impl2){
        return false;
    }
    let api1_sig = api1["api"].as_str().unwrap();
    let api2_sig = api2["api"].as_str().unwrap();
    if !compare_api(api1_sig, api2_sig){
        return false;
    }
    true
}


#[derive(Debug, PartialEq, Eq)]
struct FnSignature {
    name: String,
    body: String,
}


#[derive(Debug, PartialEq, Eq)]
struct ImplSignature {
    trait_name: String,
    struct_name: String,
    body: String,
    generics: HashSet<GenericParam>,
    trait_generics: HashSet<GenericArgument>,
    struct_generics: HashSet<GenericArgument>,
}


#[derive(Debug, PartialEq, Eq)]
pub enum ApiSignature {
    ImplTy(ImplSignature),
    FnTy(FnSignature),
}

// /// The comparison process will modify the input signatures.
// fn compare_generic_arguments(arg1: &GenericArgument, arg2: &GenericArgument) -> bool {
//     match (arg1, arg2) {
//         (GenericArgument::Type(ty1), GenericArgument::Type(ty2)) => {
//             compare_types(ty1, ty2)
//         }
//         (GenericArgument::Lifetime(lt1), GenericArgument::Lifetime(lt2)) => {
//             compare_lifetimes(lt1, lt2)
//         }
//         _ => false,
//     }
//     false
// }

/// Compare all kinds of api in string format.
pub fn compare_api(api1: &str, api2: &str) -> bool {
    let api1_sig = parse_api(api1);
    let api2_sig = parse_api(api2);
    if api1_sig.is_none() || api2_sig.is_none(){
        return api1 == api2;
    }
    let mut api1_sig = api1_sig.unwrap();
    let mut api2_sig = api2_sig.unwrap();
    // modifying the generics to be the same
    match (&mut api1_sig, &mut api2_sig) {
        (ApiSignature::ImplTy(impl1), ApiSignature::ImplTy(impl2)) => {
            return 
                impl1.trait_name == impl2.trait_name &&
                impl1.struct_name == impl2.struct_name &&
                impl1.trait_generics == impl2.trait_generics &&
                impl1.struct_generics == impl2.struct_generics;
        }
        (ApiSignature::FnTy(fn1), ApiSignature::FnTy(fn2)) => {
            return 
                fn1.name == fn2.name;
        }
        _ => (),
    }

    api1 == api2
}

// fn modify_impl_sig_generics(sig: &mut ImplSignature) {
//     for mut param in sig.generics {
//         modify_generic_params(&mut param);
//     }
//     for mut param in sig.trait_generics {
//         modify_generic_arguments(&mut param);
//     }
//     for mut param in sig.struct_generics {
//         modify_generic_arguments(&mut param);
//     }
// }

fn modify_generic_params(param: &mut GenericParam) {
    match param {
        GenericParam::Type(ty) => {
            ty.ident = syn::Ident::new("X", ty.ident.span());
        }
        GenericParam::Lifetime(lt) => {
            lt.lifetime.ident = syn::Ident::new("X", lt.lifetime.ident.span());
        }
        _ => (),
    }
}

fn modify_generic_arguments(arg: &mut GenericArgument) {
    match arg {
        GenericArgument::Type(ty) => {
            if let syn::Type::Path(path) = ty {
                if let Some(segment) = path.path.segments.first_mut() {
                    segment.ident = syn::Ident::new("X", segment.ident.span());
                }
            }
        }
        GenericArgument::Lifetime(lt) => {
            lt.ident = syn::Ident::new("X", lt.ident.span());
        }
        _ => (),
    }
}

/// Given an API signature, parse it into a struct for comparison.
/// The returned API signature includes breaking change to the generics for better analysis.
pub fn parse_api(api_sig: &str) -> Option<ApiSignature>{
    // 1. Construct a valid parsable API signature, especially for impls, functions, and types.
    let mut api_sig = {
        if api_sig.len() > 4 && &api_sig[0..4] == "impl" {
            api_sig.split("where").collect::<Vec<&str>>()[0].to_string() + "{}"
        }
        else if api_sig.contains("fn "){
            api_sig.to_string() + "{}"
        }
        else{
            api_sig.to_string()
        }
    };
    // println!("Parsing API: {:#?}", api_sig);
    let item1:syn::Item = syn::parse_str(&api_sig).ok()?;
    // println!("{:#?}", item1);
    match &item1 {
        Item::Fn(item_fn) => {
            // println!("Name: {:#?}", item_fn.sig.ident);
            // println!("Generics: {:#?}", item_fn.sig.generics);
            // println!("Inputs: {:#?}", item_fn.sig.inputs);
            // println!("Output: {:#?}", item_fn.sig.output);
            let fn_sig = FnSignature {
                name: item_fn.sig.ident.to_string(),
                body: api_sig.clone(),
            };
            return Some(ApiSignature::FnTy(fn_sig));
        }
        Item::Impl(item_impl) => {
            let mut impl_sig = ImplSignature {
                trait_name: String::new(),
                struct_name: String::new(),
                body: api_sig.clone(),
                generics: HashSet::new(),
                trait_generics: HashSet::new(),
                struct_generics: HashSet::new(),
            };
            // Impl generics + lifetime placeholders
            for param in &item_impl.generics.params{
                match param {
                    GenericParam::Type(_) |
                    GenericParam::Lifetime(_) => {
                        let mut param = param.clone();
                        modify_generic_params(&mut param);
                        impl_sig.generics.insert(param);
                    }
                    _ => (),
                }
            }
            // Trait name and generics + lifetime
            let trait_ = &item_impl.trait_.clone()?;
            impl_sig.trait_name = trait_.1.segments[0].ident.clone().to_string();
            if let PathArguments::AngleBracketed(arguments) = &trait_.1.segments[0].arguments{
                for param in &arguments.args{
                    match param {
                        GenericArgument::Type(_) |
                        GenericArgument::Lifetime(_) => {
                            let mut param = param.clone();
                            modify_generic_arguments(&mut param);
                            impl_sig.trait_generics.insert(param);
                        }
                        _ => (),
                    }
                }
            }
            // Struct name and generics + lifetime
            let target = item_impl.self_ty.clone();
            if let Type::Path(type_path) = *target {
                impl_sig.struct_name = type_path.path.segments[0].ident.to_string();
                if let PathArguments::AngleBracketed(arguments) = &type_path.path.segments[0].arguments{
                    for param in &arguments.args{
                        match param {
                            GenericArgument::Type(_) |
                            GenericArgument::Lifetime(_) => {
                                let mut param = param.clone();
                                modify_generic_arguments(&mut param);
                                impl_sig.struct_generics.insert(param);
                            }
                            _ => (),
                        }
                    }
                }
            }
            return Some(ApiSignature::ImplTy(impl_sig));
        }
        _ => return None,
    }
}



mod test {
    use std::{fs::File, io::Write};

    use super::*;

    fn test_compare(api1 : &str, api2 : &str, expected: bool){
        let result = compare_api(api1, api2);
        if(result != expected){
            let api1_sig = parse_api(api1);
            let api2_sig = parse_api(api2);
            println!("API1: {:#?}", api1_sig);
            println!("API2: {:#?}", api2_sig);
        }
        assert_eq!(result, expected);
    }


    #[test]
    fn test_parse_single_api() {
        let api = "fn min_by_key<B, F>(self, f: F) -> Option<Self::Item> -> B {}";
        let item:syn::Item = syn::parse_str(api).unwrap();
        println!("{:#?}", item);
    }

    #[test]
    fn test_parse_api() {
        // let api = "impl<I> Iterator for Intersperse<I> where I: Iterator, <I as Iterator>::Item: Clone, type Item = <I as Iterator>::Item{}";// `type cannot be successfully resolved
        // let api = "impl<I> Iterator for Intersperse<I> where I: Iterator, <I as Iterator>::Item: Clone{}";
    
        fn create_file(filename: &str, content: &str) {
            let mut file = File::create(filename).expect("Failed to create file");
            file.write_all(content.as_bytes()).expect("Failed to write to file");
        }

        let file1 = "output1.txt";
        let file2 = "output2.txt";

        let api1 = "impl<T, '_> Iterator for Drain<'_, T>"; // Same
        let api2 = "impl<'_, T> Iterator for Drain<'_, T>";
        test_compare(api1, api2, true);
        let api1 = "impl<T, U> Into for T where U: From<T>"; // Diff
        let api2 = "impl<T, U> Into<T, U> for T where U: From<T>";
        test_compare(api1, api2, false);
        let api1 = "impl<'a, F> Pattern for F where F: FnMut(char) -> bool"; // Diff
        let api2 = "impl<'a, F> Pattern<'a> for F where F: FnMut(char) -> bool";
        test_compare(api1, api2, false);
        let api1 = "impl<'a, T> Iterator for Drain<'a, T>"; // Same
        let api2 = "impl<T, '_> Iterator for Drain<'_, T>";
        test_compare(api1, api2, true);
        let api1 = "impl<K: Ord, Q: ?Sized, V, '_> Index<&'_ Q> for BTreeMap<K, V> where K: Borrow<Q>, Q: Ord"; // Same
        let api2 = "impl<'_, K: Ord, Q: ?Sized, V> Index<&'_ Q> for BTreeMap<K, V> where K: Borrow<Q>, Q: Ord";
        test_compare(api1, api2, true);
        let api1 = "impl<'_> Add<&'_ Wrapping<i128>> for Wrapping<i128>"; // Same
        let api2 = "impl Add<&'_ Wrapping<i128>> for Wrapping<i128>";
        test_compare(api1, api2, true);
        let api1 = "impl<'a> Neg for &'a Wrapping<usize>"; // Same
        let api2 = "impl<'_> Neg for &'_ Wrapping<usize>";
        test_compare(api1, api2, true);
        let api1 = "type Output = Wrapping<usize>::Output;";
        let api2 = "type Output = <Wrapping<usize> as Add<Wrapping<usize>>>::Output;";
        test_compare(api1, api2, false);
        let api1 = "fn cmp(&self, other: &Box<T>) -> Ordering";
        let api2 = "fn cmp(&self, other: &Box<T>) -> Ordering";
        test_compare(api1, api2, true);
        let api1 = "fn collect<B>(self) -> B where B: FromIterator<Self::Item>";
        let api2 = "fn collect<B>(self) -> B";
        test_compare(api1, api2, true);
        let api1 = "fn min_by_key<B, F>(self, f: F) -> Option<Self::Item> where B: Ord, F: FnMut(&Self::Item) -> B";
        let api2 = "fn min_by_key<B, F>(self, f: F) -> Option<Self::Item>";
        test_compare(api1, api2, true);
        let api1 = "impl<T, R> Clone for RadixFmt<T, R> where R: Clone + Clone, T: Clone + Clone";
        let api2 = "impl<T, R> Clone for RadixFmt<T, R> where R: Clone, T: Clone";
        test_compare(api1, api2, true);
        let api1 = "fn clone_from(&mut self, source: &Self)";
        let api2 = "fn clone_from(&mut self, source: &Self)";
        test_compare(api1, api2, true);
        // let item1:syn::Item = syn::parse_str(api1).expect("Failed to parse API signature");
        // let item2:syn::Item = syn::parse_str(api2).expect("Failed to parse API signature");
        // create_file(file1, format!("{:#?}", item1).as_str());
        // create_file(file2, format!("{:#?}", item2).as_str());
    }
}



#[allow(unused)]
fn parse_api_signature(signature: &str) -> Result<Item, syn::Error> {
    syn::parse_str(signature)
}

#[allow(unused)]
fn compare_api_signatures(sig1: &str, sig2: &str) -> bool {
    let item1 = match parse_api_signature(sig1) {
        Ok(item) => item,
        Err(_) => return false, // Return false if parsing fails
    };
    let item2 = match parse_api_signature(sig2) {
        Ok(item) => item,
        Err(_) => return false, // Return false if parsing fails
    };

    // Compare relevant parts of the API signatures
    match (&item1, &item2) {
        (Item::Fn(item_fn1), Item::Fn(item_fn2)) => {
            // Compare function names
            if item_fn1.sig.ident != item_fn2.sig.ident {
                return false;
            }

            // Compare parameter types
            if item_fn1.sig.inputs.len() != item_fn2.sig.inputs.len() {
                return false;
            }
            for (param1, param2) in item_fn1.sig.inputs.iter().zip(item_fn2.sig.inputs.iter()) {
                if !compare_types(&param1, &param2) {
                    return false;
                }
            }

            // Compare return types
            if !compare_return_types(&item_fn1.sig.output, &item_fn2.sig.output) {
                return false;
            }

            // Compare generics if needed

            // If all comparisons passed, return true
            true
        }
        _ => false, // Return false if items are not functions
    }
}

#[allow(unused)]
fn compare_types(type1: &syn::FnArg, type2: &syn::FnArg) -> bool {
    // Compare types of function arguments
    // Implement as needed
    true
}

#[allow(unused)]
fn compare_return_types(type1: &ReturnType, type2: &ReturnType) -> bool {
    // Compare return types of functions
    // Implement as needed
    true
}